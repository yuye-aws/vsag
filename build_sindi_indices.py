#!/usr/bin/env python3
"""
Build SINDI indices for MSMarco v1 and Natural Questions datasets
Creates 4 indices:
1. MSMarco v1 without pruning (alpha=1.0)
2. MSMarco v1 with pruning (alpha=0.3)
3. Natural Questions without pruning (alpha=1.0)
4. Natural Questions with pruning (alpha=0.3)
"""

import subprocess
import os
import time
from datetime import datetime

# Configuration
SINDI_BUILD_BIN = "/home/ec2-user/Code/vsag/build-release/sparse/scripts/sindi_index_build"
LAMBDA = 1000  # window_size parameter

# Dataset configurations
DATASETS = [
    {
        "name": "msmarco_v1",
        "docs_csr": "/home/ec2-user/sparse_datasets/msmarco_v1_cocondenser/docs.csr",
        "queries_csr": "/home/ec2-user/sparse_datasets/msmarco_v1_cocondenser/queries.csr",
    },
    {
        "name": "nq",
        "docs_csr": "/home/ec2-user/sparse_datasets/nq_cocondenser/nq_docs.csr",
        "queries_csr": "/home/ec2-user/sparse_datasets/nq_cocondenser/nq_queries.csr",
    }
]

# Pruning configurations
PRUNING_CONFIGS = [
    {"alpha": 1.0, "suffix": "no_prune"},
    {"alpha": 0.3, "suffix": "alpha_0.3"}
]

def run_command(cmd, description):
    """Run a shell command and capture output"""
    print(f"\n{'='*60}")
    print(f"{description}")
    print(f"{'='*60}")
    print(f"Command: {' '.join(cmd)}")
    print()
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        elapsed = time.time() - start_time
        
        print(result.stdout)
        print(f"\n✓ Completed in {elapsed:.2f} seconds")
        
        return True, elapsed, result.stdout
        
    except subprocess.CalledProcessError as e:
        elapsed = time.time() - start_time
        print(f"✗ Error: {e}")
        print(e.stdout)
        print(f"\nFailed after {elapsed:.2f} seconds")
        
        return False, elapsed, e.stdout

def get_file_size_mb(filepath):
    """Get file size in MB"""
    if os.path.exists(filepath):
        return os.path.getsize(filepath) / (1024 * 1024)
    return 0

def build_index(dataset, alpha, suffix):
    """Build a SINDI index with given parameters"""
    
    dataset_name = dataset["name"]
    docs_csr = dataset["docs_csr"]
    
    # Check if input file exists
    if not os.path.exists(docs_csr):
        print(f"✗ Error: Input file not found: {docs_csr}")
        return None
    
    # Output index path
    index_path = f"{dataset_name}_sindi_{suffix}.index"
    
    # Build command
    cmd = [
        SINDI_BUILD_BIN,
        docs_csr,
        str(LAMBDA),
        str(alpha),
        index_path
    ]
    
    description = f"Building {dataset_name} index with alpha={alpha} (lambda={LAMBDA})"
    
    success, elapsed, output = run_command(cmd, description)
    
    if success:
        index_size_mb = get_file_size_mb(index_path)
        
        return {
            "dataset": dataset_name,
            "alpha": alpha,
            "lambda": LAMBDA,
            "index_path": index_path,
            "build_time_sec": elapsed,
            "index_size_mb": index_size_mb,
            "success": True
        }
    else:
        return {
            "dataset": dataset_name,
            "alpha": alpha,
            "lambda": LAMBDA,
            "index_path": index_path,
            "success": False
        }

def main():
    print("="*60)
    print("SINDI Index Building Script")
    print("="*60)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nDatasets: {len(DATASETS)}")
    print(f"Pruning configs: {len(PRUNING_CONFIGS)}")
    print(f"Total indices to build: {len(DATASETS) * len(PRUNING_CONFIGS)}")
    print()
    
    # Check if build binary exists
    if not os.path.exists(SINDI_BUILD_BIN):
        print(f"✗ Error: SINDI build binary not found: {SINDI_BUILD_BIN}")
        return
    
    results = []
    
    # Build all indices
    for dataset in DATASETS:
        for config in PRUNING_CONFIGS:
            result = build_index(
                dataset,
                config["alpha"],
                config["suffix"]
            )
            
            if result:
                results.append(result)
    
    # Print summary
    print("\n" + "="*60)
    print("BUILD SUMMARY")
    print("="*60)
    
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    
    print(f"\nTotal indices built: {len(successful)}/{len(results)}")
    
    if successful:
        print("\n✓ Successfully built indices:")
        print(f"{'Dataset':<15} {'Alpha':<8} {'Build Time':<12} {'Size (MB)':<12} {'Index Path'}")
        print("-" * 80)
        
        for r in successful:
            print(f"{r['dataset']:<15} {r['alpha']:<8.1f} {r['build_time_sec']:<12.2f} "
                  f"{r['index_size_mb']:<12.2f} {r['index_path']}")
    
    if failed:
        print("\n✗ Failed builds:")
        for r in failed:
            print(f"  - {r['dataset']} (alpha={r['alpha']})")
    
    print("\n" + "="*60)
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Save results to file
    results_file = "sindi_build_results.txt"
    with open(results_file, "w") as f:
        f.write("SINDI Index Build Results\n")
        f.write("="*60 + "\n")
        f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        for r in results:
            f.write(f"Dataset: {r['dataset']}\n")
            f.write(f"Alpha: {r['alpha']}\n")
            f.write(f"Lambda: {r['lambda']}\n")
            f.write(f"Index Path: {r['index_path']}\n")
            f.write(f"Success: {r['success']}\n")
            
            if r['success']:
                f.write(f"Build Time: {r['build_time_sec']:.2f} seconds\n")
                f.write(f"Index Size: {r['index_size_mb']:.2f} MB\n")
            
            f.write("\n")
    
    print(f"\nResults saved to: {results_file}")

if __name__ == "__main__":
    main()
