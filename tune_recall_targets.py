#!/usr/bin/env python3
"""
Tune SINDI search hyperparameters to achieve target recall levels
Finds optimal beta and gamma values for 91%, 93%, 95%, 97%, 99% recall
"""

import subprocess
import re
import time
from datetime import datetime
from collections import defaultdict

# Configuration
SEARCH_BIN = "/home/ec2-user/Code/vsag/build-release/sparse/scripts/sindi_index_search"
INDEX_PATH = "msmarco_v1_sindi_no_prune.index"
QUERIES_CSR = "/home/ec2-user/sparse_datasets/msmarco_v1_cocondenser/queries.csr"
GT_FILE = "msmarco_v1_gt.bin"
TOPK = 10
NUM_THREADS = 1

# Target recalls to achieve
TARGET_RECALLS = [0.91, 0.93, 0.95, 0.97, 0.99]

# Search space for hyperparameters
BETA_VALUES = [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
GAMMA_VALUES = [5, 10, 15, 20, 30, 40, 50, 75, 100, 150, 200, 300, 400, 500, 700, 1000, 1500, 2000]

def run_search(beta, gamma, verbose=False):
    """Run search with given beta and gamma, return recall, QPS, and latency"""
    
    cmd = [
        SEARCH_BIN,
        INDEX_PATH,
        QUERIES_CSR,
        GT_FILE,
        str(beta),
        str(gamma),
        str(TOPK),
        str(NUM_THREADS)
    ]
    
    try:
        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        output = result.stdout
        
        if verbose:
            print(output)
        
        # Parse recall and QPS from output
        recall_match = re.search(r'recall[:\s]+([0-9.]+)', output, re.IGNORECASE)
        qps_match = re.search(r'qps[:\s]+([0-9.]+)', output, re.IGNORECASE)
        
        if recall_match and qps_match:
            recall = float(recall_match.group(1))
            qps = float(qps_match.group(1))
            latency_ms = 1000.0 / qps if qps > 0 else float('inf')
            return recall, qps, latency_ms, True
        else:
            return None, None, None, False
            
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        return None, None, None, False

def format_recall_pct(recall):
    """Format recall as percentage"""
    return f"{recall*100:.1f}%"

def find_best_configs_for_targets(results, target_recalls):
    """Find best configuration (lowest latency) for each target recall"""
    
    best_configs = {}
    
    for target in target_recalls:
        # Find all configs that meet or exceed target recall
        candidates = [
            (r['recall'], r['qps'], r['latency_ms'], r['beta'], r['gamma'])
            for r in results
            if r['recall'] >= target
        ]
        
        if candidates:
            # Sort by latency (ascending) to get lowest latency
            candidates.sort(key=lambda x: x[2])
            best_recall, best_qps, best_latency, best_beta, best_gamma = candidates[0]
            
            best_configs[target] = {
                'beta': best_beta,
                'gamma': best_gamma,
                'recall': best_recall,
                'qps': best_qps,
                'latency_ms': best_latency
            }
    
    return best_configs

def smart_search_for_target(target_recall, beta_value, verbose=False):
    """
    Smart binary search for gamma given a beta value
    Finds minimum gamma that achieves target recall
    """
    
    gamma_min = 5
    gamma_max = 2000
    best_config = None
    
    # Try a few gamma values with binary search approach
    tested_gammas = set()
    
    for _ in range(10):  # Max 10 iterations
        gamma = (gamma_min + gamma_max) // 2
        
        # Round to nearest "nice" value
        if gamma < 20:
            gamma = round(gamma / 5) * 5
        elif gamma < 100:
            gamma = round(gamma / 10) * 10
        elif gamma < 200:
            gamma = round(gamma / 25) * 25
        elif gamma < 1000:
            gamma = round(gamma / 50) * 50
        else:
            gamma = round(gamma / 100) * 100
        
        if gamma in tested_gammas:
            break
        
        tested_gammas.add(gamma)
        
        if verbose:
            print(f"  Testing gamma={gamma}...", end=" ", flush=True)
        
        recall, qps, latency_ms, success = run_search(beta_value, gamma, verbose=False)
        
        if not success:
            if verbose:
                print("FAILED")
            gamma_min = gamma + 1
            continue
        
        if verbose:
            print(f"recall={format_recall_pct(recall)}, latency={latency_ms:.2f}ms")
        
        if recall >= target_recall:
            # Found a config that works
            if best_config is None or gamma < best_config['gamma']:
                best_config = {
                    'beta': beta_value,
                    'gamma': gamma,
                    'recall': recall,
                    'qps': qps,
                    'latency_ms': latency_ms
                }
            gamma_max = gamma - 1
        else:
            gamma_min = gamma + 1
        
        if gamma_max <= gamma_min:
            break
    
    return best_config

def fast_tune(target_recalls, verbose=True):
    """
    Fast tuning strategy: test strategic beta values and find optimal gamma
    """
    
    print("="*70)
    print("FAST TUNING MODE")
    print("="*70)
    print(f"Strategy: Test strategic beta values, find optimal gamma for each target")
    print(f"Target recalls: {', '.join([format_recall_pct(t) for t in target_recalls])}")
    print()
    
    # Strategic beta values to test (fewer but well-chosen)
    strategic_betas = [0.1, 0.2, 0.3, 0.4, 0.5]
    
    all_configs = defaultdict(list)
    
    for target in target_recalls:
        print(f"\n{'='*70}")
        print(f"Finding configurations for target recall: {format_recall_pct(target)}")
        print(f"{'='*70}")
        
        for beta in strategic_betas:
            print(f"\nTesting beta={beta}:")
            config = smart_search_for_target(target, beta, verbose=verbose)
            
            if config:
                all_configs[target].append(config)
                print(f"  ✓ Found: beta={config['beta']}, gamma={config['gamma']}, "
                      f"recall={format_recall_pct(config['recall'])}, latency={config['latency_ms']:.2f}ms")
            else:
                print(f"  ✗ Could not achieve target with beta={beta}")
    
    return all_configs

def comprehensive_tune(beta_values, gamma_values, verbose=True):
    """
    Comprehensive grid search: test all beta/gamma combinations
    """
    
    print("="*70)
    print("COMPREHENSIVE GRID SEARCH MODE")
    print("="*70)
    print(f"Testing {len(beta_values)} beta values × {len(gamma_values)} gamma values")
    print(f"Total configurations: {len(beta_values) * len(gamma_values)}")
    print(f"Estimated time: ~{len(beta_values) * len(gamma_values) * 2 / 60:.0f} minutes")
    print()
    
    results = []
    total_tests = len(beta_values) * len(gamma_values)
    test_num = 0
    
    start_time = time.time()
    
    for beta in beta_values:
        for gamma in gamma_values:
            test_num += 1
            
            if verbose:
                print(f"[{test_num}/{total_tests}] Testing beta={beta}, gamma={gamma}...", 
                      end=" ", flush=True)
            
            recall, qps, latency_ms, success = run_search(beta, gamma, verbose=False)
            
            if success:
                results.append({
                    'beta': beta,
                    'gamma': gamma,
                    'recall': recall,
                    'qps': qps,
                    'latency_ms': latency_ms
                })
                
                if verbose:
                    print(f"recall={format_recall_pct(recall)}, latency={latency_ms:.2f}ms")
            else:
                if verbose:
                    print("FAILED")
    
    elapsed = time.time() - start_time
    print(f"\nCompleted {len(results)}/{total_tests} tests in {elapsed/60:.1f} minutes")
    
    return results

def print_recommendations(all_configs, target_recalls):
    """Print recommendations for each target recall"""
    
    print("\n" + "="*70)
    print("RECOMMENDATIONS")
    print("="*70)
    
    for target in target_recalls:
        print(f"\n{'='*70}")
        print(f"Target Recall: {format_recall_pct(target)}")
        print(f"{'='*70}")
        
        if target not in all_configs or not all_configs[target]:
            print("✗ No configuration found to achieve this target")
            print("  Suggestion: Rebuild index with higher alpha (e.g., 0.9 or 1.0)")
            continue
        
        # Sort by latency (ascending)
        configs = sorted(all_configs[target], key=lambda x: x['latency_ms'])
        
        # Show best config (lowest latency)
        best = configs[0]
        print(f"\n⭐ RECOMMENDED (Lowest Latency):")
        print(f"  Beta: {best['beta']}")
        print(f"  Gamma: {best['gamma']}")
        print(f"  Achieved Recall: {format_recall_pct(best['recall'])}")
        print(f"  Latency: {best['latency_ms']:.2f} ms")
        print(f"  QPS: {best['qps']:.1f}")
        print(f"\n  Command:")
        print(f"  ./build-release/sparse/scripts/sindi_index_search \\")
        print(f"      {INDEX_PATH} \\")
        print(f"      {QUERIES_CSR} \\")
        print(f"      {GT_FILE} {best['beta']} {best['gamma']} {TOPK} {NUM_THREADS}")
        
        # Show alternatives if available
        if len(configs) > 1:
            print(f"\n  Alternatives:")
            for i, cfg in enumerate(configs[1:4], 1):  # Show up to 3 alternatives
                print(f"    {i}. beta={cfg['beta']}, gamma={cfg['gamma']}, "
                      f"recall={format_recall_pct(cfg['recall'])}, latency={cfg['latency_ms']:.2f}ms")

def save_results(results, filename="recall_tuning_results.txt"):
    """Save all results to file"""
    
    with open(filename, "w") as f:
        f.write("SINDI Recall Tuning Results\n")
        f.write("="*70 + "\n")
        f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Index: {INDEX_PATH}\n")
        f.write(f"Queries: {QUERIES_CSR}\n")
        f.write(f"Ground Truth: {GT_FILE}\n")
        f.write(f"Top-K: {TOPK}\n")
        f.write(f"Threads: {NUM_THREADS}\n")
        f.write("\n")
        
        f.write(f"{'Beta':<8} {'Gamma':<8} {'Recall':<10} {'Latency(ms)':<12} {'QPS':<10}\n")
        f.write("-"*70 + "\n")
        
        # Sort by recall, then by latency
        sorted_results = sorted(results, key=lambda x: (x['recall'], x['latency_ms']), reverse=True)
        
        for r in sorted_results:
            f.write(f"{r['beta']:<8.2f} {r['gamma']:<8} "
                   f"{format_recall_pct(r['recall']):<10} {r['latency_ms']:<12.2f} {r['qps']:<10.1f}\n")
    
    print(f"\nDetailed results saved to: {filename}")

def main():
    import argparse
    
    # Declare globals at the start
    global INDEX_PATH, QUERIES_CSR, GT_FILE
    
    parser = argparse.ArgumentParser(
        description="Tune SINDI search hyperparameters for target recalls"
    )
    parser.add_argument(
        "--mode",
        choices=["fast", "comprehensive"],
        default="fast",
        help="Tuning mode: 'fast' for strategic search, 'comprehensive' for grid search"
    )
    parser.add_argument(
        "--index",
        default=INDEX_PATH,
        help=f"Path to index file (default: {INDEX_PATH})"
    )
    parser.add_argument(
        "--queries",
        default=QUERIES_CSR,
        help=f"Path to queries CSR file (default: {QUERIES_CSR})"
    )
    parser.add_argument(
        "--gt",
        default=GT_FILE,
        help=f"Path to ground truth file (default: {GT_FILE})"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce output verbosity"
    )
    
    args = parser.parse_args()
    
    # Update global config from args
    INDEX_PATH = args.index
    QUERIES_CSR = args.queries
    GT_FILE = args.gt
    
    verbose = not args.quiet
    
    print("="*70)
    print("SINDI RECALL TUNING SCRIPT")
    print("="*70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {args.mode.upper()}")
    print(f"Index: {INDEX_PATH}")
    print(f"Queries: {QUERIES_CSR}")
    print(f"Ground Truth: {GT_FILE}")
    print()
    
    start_time = time.time()
    
    if args.mode == "fast":
        # Fast tuning mode
        all_configs = fast_tune(TARGET_RECALLS, verbose=verbose)
        print_recommendations(all_configs, TARGET_RECALLS)
        
    else:
        # Comprehensive mode
        results = comprehensive_tune(BETA_VALUES, GAMMA_VALUES, verbose=verbose)
        
        if results:
            # Save detailed results
            save_results(results)
            
            # Find best configs for each target
            all_configs = find_best_configs_for_targets(results, TARGET_RECALLS)
            print_recommendations(all_configs, TARGET_RECALLS)
    
    elapsed = time.time() - start_time
    
    print("\n" + "="*70)
    print(f"Total time: {elapsed/60:.1f} minutes")
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

if __name__ == "__main__":
    main()
