#!/usr/bin/env python3
"""
Tune SINDI beta parameter using binary search with fixed gamma=500
Performs binary search between 0.0 and 1.0 for beta value with 10 iterations
"""

import subprocess
import re
import time
from datetime import datetime
import os
import argparse

# Configuration
SEARCH_BIN = "/home/ec2-user/Code/vsag/build-release/sparse/scripts/sindi_index_search"
TOPK = 10
NUM_THREADS = 1
FIXED_GAMMA = 500
BINARY_SEARCH_ITERATIONS = 10

# Index configurations
INDEX_CONFIGS = [
    {
        "name": "msmarco_v2_no_prune",
        "index_path": "msmarco_v2_sindi_no_prune.index",
        "queries_csr": "/home/ec2-user/sparse_datasets/msmarco_v2/queries.csr",
        "gt_file": "msmarco_v2_gt_corrected.bin",
        "alpha": 1.0
    },
    {
        "name": "msmarco_v1",
        "index_path": "msmarco_v1_sindi.index",
        "queries_csr": "/home/ec2-user/sparse_datasets/msmarco_v1_cocondenser_converted/queries.csr",
        "gt_file": "msmarco_v1_gt.bin",
        "alpha": 1.0
    }
]

# Target recalls to achieve
TARGET_RECALLS = [0.91, 0.93, 0.95, 0.97, 0.99]


def run_search(index_path, queries_csr, gt_file, beta, gamma, verbose=False):
    """Run search with given beta and gamma, return recall, QPS, and latency"""
    
    cmd = [
        SEARCH_BIN,
        index_path,
        queries_csr,
        gt_file,
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
            timeout=1800  # 30 minute timeout
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
            latency_us = 1000000.0 / qps if qps > 0 else float('inf')
            return recall, qps, latency_us, True
        else:
            return None, None, None, False
    
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        return None, None, None, False


def format_recall_pct(recall):
    """Format recall as percentage"""
    return f"{recall*100:.1f}%"


def binary_search_beta(index_path, queries_csr, gt_file, target_recall, gamma, 
                       beta_min=0.0, beta_max=1.0, max_iterations=10, verbose=True):
    """
    Binary search for optimal beta value that achieves target recall
    with fixed gamma value
    
    Args:
        index_path: Path to index file
        queries_csr: Path to queries CSR file
        gt_file: Path to ground truth file
        target_recall: Target recall to achieve
        gamma: Fixed gamma value
        beta_min: Minimum beta value (default: 0.0)
        beta_max: Maximum beta value (default: 1.0)
        max_iterations: Number of binary search iterations (default: 10)
        verbose: Print detailed progress
    
    Returns:
        Dictionary with best configuration or None if target not achievable
    """
    
    if verbose:
        print(f"\n{'='*70}")
        print(f"Binary Search for Target Recall: {format_recall_pct(target_recall)}")
        print(f"{'='*70}")
        print(f"Fixed gamma: {gamma}")
        print(f"Beta range: [{beta_min:.4f}, {beta_max:.4f}]")
        print(f"Max iterations: {max_iterations}")
        print()
    
    best_config = None
    iteration_results = []
    
    for iteration in range(max_iterations):
        # Calculate midpoint
        beta = (beta_min + beta_max) / 2.0
        
        if verbose:
            print(f"Iteration {iteration + 1}/{max_iterations}: Testing beta={beta:.4f}...", 
                  end=" ", flush=True)
        
        recall, qps, latency_us, success = run_search(
            index_path, queries_csr, gt_file, beta, gamma, verbose=False
        )
        
        if not success:
            if verbose:
                print("FAILED")
            # If search failed, try lower beta
            beta_max = beta
            continue
        
        iteration_results.append({
            'iteration': iteration + 1,
            'beta': beta,
            'gamma': gamma,
            'recall': recall,
            'qps': qps,
            'latency_us': latency_us
        })
        
        if verbose:
            print(f"recall={format_recall_pct(recall)}, latency={latency_us:.2f}us, QPS={qps:.1f}")
        
        # Check if we achieved target recall
        if recall >= target_recall:
            # Target achieved, try lower beta for better performance
            if best_config is None or beta < best_config['beta']:
                best_config = {
                    'beta': beta,
                    'gamma': gamma,
                    'recall': recall,
                    'qps': qps,
                    'latency_us': latency_us,
                    'iteration': iteration + 1
                }
            beta_max = beta
        else:
            # Target not achieved, need higher beta
            beta_min = beta
        
        # Check convergence
        if abs(beta_max - beta_min) < 0.0001:
            if verbose:
                print(f"\nConverged after {iteration + 1} iterations")
            break
    
    if verbose:
        print(f"\n{'='*70}")
        if best_config:
            print(f"✓ Target {format_recall_pct(target_recall)} ACHIEVED")
            print(f"  Best beta: {best_config['beta']:.4f}")
            print(f"  Achieved recall: {format_recall_pct(best_config['recall'])}")
            print(f"  Latency: {best_config['latency_us']:.2f} us")
            print(f"  QPS: {best_config['qps']:.1f}")
            print(f"  Found at iteration: {best_config['iteration']}")
        else:
            print(f"✗ Target {format_recall_pct(target_recall)} NOT ACHIEVED")
            print(f"  Maximum recall observed: {max([r['recall'] for r in iteration_results]) if iteration_results else 0:.4f}")
        print(f"{'='*70}")
    
    return best_config, iteration_results


def tune_index(index_config, target_recalls, gamma, iterations=10, verbose=True):
    """
    Tune beta for multiple target recalls on a single index
    """
    
    index_path = index_config['index_path']
    queries_csr = index_config['queries_csr']
    gt_file = index_config['gt_file']
    
    print("\n" + "="*70)
    print(f"TUNING INDEX: {index_config['name']}")
    print("="*70)
    print(f"Index: {index_path}")
    print(f"Alpha: {index_config['alpha']}")
    print(f"Fixed Gamma: {gamma}")
    print(f"Binary Search Iterations: {iterations}")
    print(f"Target Recalls: {', '.join([format_recall_pct(t) for t in target_recalls])}")
    print("="*70)
    
    all_results = {}
    
    for target in target_recalls:
        start_time = time.time()
        
        best_config, iteration_results = binary_search_beta(
            index_path, queries_csr, gt_file, target, gamma,
            beta_min=0.0, beta_max=1.0,
            max_iterations=iterations,
            verbose=verbose
        )
        
        elapsed = time.time() - start_time
        
        all_results[target] = {
            'best_config': best_config,
            'iteration_results': iteration_results,
            'elapsed_time': elapsed
        }
        
        if verbose:
            print(f"⏱ Time for target {format_recall_pct(target)}: {elapsed:.1f} seconds\n")
    
    return all_results


def print_summary(index_config, all_results, target_recalls, gamma):
    """Print summary of all results"""
    
    print("\n" + "="*70)
    print(f"SUMMARY: {index_config['name']}")
    print("="*70)
    print(f"Fixed Gamma: {gamma}")
    print()
    
    print(f"{'Target':<12} {'Beta':<10} {'Achieved':<12} {'Latency(us)':<14} {'QPS':<10} {'Status':<10}")
    print("-"*70)
    
    for target in target_recalls:
        result = all_results[target]
        best = result['best_config']
        
        if best:
            print(f"{format_recall_pct(target):<12} "
                  f"{best['beta']:<10.4f} "
                  f"{format_recall_pct(best['recall']):<12} "
                  f"{best['latency_us']:<14.2f} "
                  f"{best['qps']:<10.1f} "
                  f"{'✓ SUCCESS':<10}")
        else:
            max_recall = max([r['recall'] for r in result['iteration_results']]) if result['iteration_results'] else 0
            print(f"{format_recall_pct(target):<12} "
                  f"{'N/A':<10} "
                  f"{format_recall_pct(max_recall):<12} "
                  f"{'N/A':<14} "
                  f"{'N/A':<10} "
                  f"{'✗ FAILED':<10}")
    
    print()
    
    # Print commands for successful configurations
    print("RECOMMENDED COMMANDS:")
    print("-"*70)
    
    for target in target_recalls:
        result = all_results[target]
        best = result['best_config']
        
        if best:
            print(f"\n# Target recall: {format_recall_pct(target)}")
            print(f"./build-release/sparse/scripts/sindi_index_search \\")
            print(f"    {index_config['index_path']} \\")
            print(f"    {index_config['queries_csr']} \\")
            print(f"    {index_config['gt_file']} \\")
            print(f"    {best['beta']:.4f} {best['gamma']} {TOPK} {NUM_THREADS}")


def save_detailed_results(index_config, all_results, target_recalls, gamma, iterations, filename):
    """Save detailed results to file"""
    
    with open(filename, "w") as f:
        f.write(f"SINDI Beta Binary Search Results: {index_config['name']}\n")
        f.write("="*70 + "\n")
        f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Index: {index_config['index_path']}\n")
        f.write(f"Alpha: {index_config['alpha']}\n")
        f.write(f"Fixed Gamma: {gamma}\n")
        f.write(f"Binary Search Iterations: {iterations}\n")
        f.write(f"Top-K: {TOPK}\n")
        f.write(f"Threads: {NUM_THREADS}\n")
        f.write("\n")
        
        for target in target_recalls:
            result = all_results[target]
            best = result['best_config']
            
            f.write(f"\n{'='*70}\n")
            f.write(f"Target Recall: {format_recall_pct(target)}\n")
            f.write(f"{'='*70}\n")
            
            if best:
                f.write(f"✓ TARGET ACHIEVED\n")
                f.write(f"  Best Beta: {best['beta']:.4f}\n")
                f.write(f"  Gamma: {best['gamma']}\n")
                f.write(f"  Achieved Recall: {format_recall_pct(best['recall'])}\n")
                f.write(f"  Latency: {best['latency_us']:.2f} us\n")
                f.write(f"  QPS: {best['qps']:.1f}\n")
                f.write(f"  Found at iteration: {best['iteration']}\n")
            else:
                f.write(f"✗ TARGET NOT ACHIEVED\n")
            
            f.write(f"\nIteration Details:\n")
            f.write(f"{'Iter':<6} {'Beta':<10} {'Recall':<10} {'Latency(us)':<14} {'QPS':<10}\n")
            f.write("-"*70 + "\n")
            
            for iter_result in result['iteration_results']:
                f.write(f"{iter_result['iteration']:<6} "
                       f"{iter_result['beta']:<10.4f} "
                       f"{format_recall_pct(iter_result['recall']):<10} "
                       f"{iter_result['latency_us']:<14.2f} "
                       f"{iter_result['qps']:<10.1f}\n")
            
            f.write(f"\nTime: {result['elapsed_time']:.1f} seconds\n")
    
    print(f"\nDetailed results saved to: {filename}")


def main():
    parser = argparse.ArgumentParser(
        description="Tune SINDI beta parameter using binary search with fixed gamma=500"
    )
    parser.add_argument(
        "--gamma",
        type=int,
        default=500,
        help="Fixed gamma value (default: 500)"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=10,
        help="Number of binary search iterations (default: 10)"
    )
    parser.add_argument(
        "--targets",
        nargs="+",
        type=float,
        default=None,
        help="Target recall values (default: 0.91, 0.93, 0.95, 0.97, 0.99)"
    )
    parser.add_argument(
        "--index",
        choices=[cfg['name'] for cfg in INDEX_CONFIGS] + ["all"],
        default="all",
        help="Which index to tune (default: all)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce output verbosity"
    )
    
    args = parser.parse_args()
    
    # Set parameters from args
    gamma = args.gamma
    iterations = args.iterations
    target_recalls = sorted(args.targets) if args.targets else [0.91, 0.93, 0.95, 0.97, 0.99]
    
    verbose = not args.quiet
    
    # Determine which indices to process
    if args.index == "all":
        indices_to_process = INDEX_CONFIGS
    else:
        indices_to_process = [cfg for cfg in INDEX_CONFIGS if cfg['name'] == args.index]
    
    # Filter to only existing index files
    available_indices = []
    for cfg in indices_to_process:
        if os.path.exists(cfg['index_path']):
            available_indices.append(cfg)
        else:
            print(f"⚠ Warning: Index file not found: {cfg['index_path']}, skipping...")
    
    if not available_indices:
        print("✗ Error: No valid index files found!")
        print("\nPlease ensure index files exist or run build_sindi_indices.py first.")
        return
    
    print("="*70)
    print("SINDI BETA BINARY SEARCH TUNING")
    print("="*70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Fixed Gamma: {gamma}")
    print(f"Binary Search Iterations: {iterations}")
    print(f"Target Recalls: {', '.join([format_recall_pct(t) for t in target_recalls])}")
    print(f"Indices to process: {len(available_indices)}")
    for cfg in available_indices:
        print(f"  - {cfg['name']} (alpha={cfg['alpha']})")
    print("="*70)
    
    overall_start_time = time.time()
    
    # Process each index
    for idx, index_config in enumerate(available_indices, 1):
        print(f"\n{'='*70}")
        print(f"PROCESSING INDEX {idx}/{len(available_indices)}")
        print(f"{'='*70}")
        
        start_time = time.time()
        
        all_results = tune_index(
            index_config, target_recalls, gamma, iterations, verbose=verbose
        )
        
        print_summary(index_config, all_results, target_recalls, gamma)
        
        # Save detailed results
        filename = f"beta_binary_search_{index_config['name']}_gamma{gamma}.txt"
        save_detailed_results(index_config, all_results, target_recalls, gamma, iterations, filename)
        
        elapsed = time.time() - start_time
        print(f"\n⏱ Total time for {index_config['name']}: {elapsed/60:.1f} minutes")
    
    overall_elapsed = time.time() - overall_start_time
    
    print("\n" + "="*70)
    print("ALL INDICES COMPLETED")
    print("="*70)
    print(f"Total indices processed: {len(available_indices)}")
    print(f"Total time: {overall_elapsed/60:.1f} minutes")
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)


if __name__ == "__main__":
    main()
