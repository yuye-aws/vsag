#!/usr/bin/env python3
"""
Build SINDI indices for MSMarco v1 and Natural Questions datasets
Creates 4 indices:
1. MSMarco v1 without pruning (alpha=1.0)
2. MSMarco v1 with pruning (alpha=0.3)
3. Natural Questions without pruning (alpha=1.0)
4. Natural Questions with pruning (alpha=0.3)

Benchmarks single-threaded build time and extracts memory statistics.
"""

import subprocess
import os
import time
import re
from datetime import datetime

# Configuration
SINDI_BUILD_BIN = "/home/ec2-user/Code/vsag/build-release/sparse/scripts/sindi_index_build"
LAMBDA = 1000  # window_size parameter
NUM_THREADS = 1  # Single-threaded for consistent benchmarking

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

def parse_memory_stats(output):
    """Parse memory statistics from C++ program output"""
    stats = {
        'posting_list_mb': None,
        'forward_index_mb': None,
        'total_memory_mb': None,
        'posting_list_nnz': None,
        'forward_index_nnz': None,
        'total_documents': None,
        'vocabulary_size': None,
        'build_time_from_output': None
    }
    
    # Parse posting list memory (MB)
    match = re.search(r'POSTING LIST.*?Memory:\s+([\d.]+)\s+MB', output, re.DOTALL)
    if match:
        stats['posting_list_mb'] = float(match.group(1))
    
    # Parse forward index memory (MB)
    match = re.search(r'FORWARD INDEX MEMORY.*?Memory:\s+([\d.]+)\s+MB', output, re.DOTALL)
    if match:
        stats['forward_index_mb'] = float(match.group(1))
    
    # Parse total memory (MB)
    match = re.search(r'TOTAL MEMORY.*?Total:\s+([\d.]+)\s+MB', output, re.DOTALL)
    if match:
        stats['total_memory_mb'] = float(match.group(1))
    
    # Parse posting list non-zeros
    match = re.search(r'POSTING LIST.*?Total non-zeros:\s+(\d+)', output, re.DOTALL)
    if match:
        stats['posting_list_nnz'] = int(match.group(1))
    
    # Parse forward index non-zeros
    match = re.search(r'FORWARD INDEX MEMORY.*?Total non-zeros:\s+(\d+)', output, re.DOTALL)
    if match:
        stats['forward_index_nnz'] = int(match.group(1))
    
    # Parse total documents
    match = re.search(r'Total documents:\s+(\d+)', output)
    if match:
        stats['total_documents'] = int(match.group(1))
    
    # Parse vocabulary size
    match = re.search(r'Vocabulary size:\s+(\d+)', output)
    if match:
        stats['vocabulary_size'] = int(match.group(1))
    
    # Parse build time from output
    match = re.search(r'Build time:\s+([\d.]+)\s+seconds', output)
    if match:
        stats['build_time_from_output'] = float(match.group(1))
    
    return stats

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
    
    # Build command (with single thread for benchmarking)
    cmd = [
        SINDI_BUILD_BIN,
        docs_csr,
        str(LAMBDA),
        str(alpha),
        index_path,
        str(NUM_THREADS)  # Explicitly set thread count for benchmarking
    ]
    
    description = f"Building {dataset_name} index with alpha={alpha} (lambda={LAMBDA})"
    
    success, elapsed, output = run_command(cmd, description)
    
    if success:
        index_size_mb = get_file_size_mb(index_path)
        memory_stats = parse_memory_stats(output)
        
        return {
            "dataset": dataset_name,
            "alpha": alpha,
            "lambda": LAMBDA,
            "index_path": index_path,
            "build_time_sec": elapsed,
            "index_size_mb": index_size_mb,
            "posting_list_mb": memory_stats['posting_list_mb'],
            "forward_index_mb": memory_stats['forward_index_mb'],
            "total_memory_mb": memory_stats['total_memory_mb'],
            "posting_list_nnz": memory_stats['posting_list_nnz'],
            "forward_index_nnz": memory_stats['forward_index_nnz'],
            "total_documents": memory_stats['total_documents'],
            "vocabulary_size": memory_stats['vocabulary_size'],
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
    print(f"Thread count: {NUM_THREADS} (single-threaded for benchmarking)")
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
        print(f"{'Dataset':<15} {'Alpha':<8} {'Build Time':<12} {'Posting List':<14} {'Forward Idx':<14} {'Total Size':<12}")
        print(f"{'':15} {'':8} {'(seconds)':<12} {'(MB)':<14} {'(MB)':<14} {'(MB)':<12}")
        print("-" * 95)
        
        for r in successful:
            posting_mb = f"{r['posting_list_mb']:.2f}" if r['posting_list_mb'] is not None else "N/A"
            forward_mb = f"{r['forward_index_mb']:.2f}" if r['forward_index_mb'] is not None else "N/A"
            total_mb = f"{r['total_memory_mb']:.2f}" if r['total_memory_mb'] is not None else f"{r['index_size_mb']:.2f}"
            
            print(f"{r['dataset']:<15} {r['alpha']:<8.1f} {r['build_time_sec']:<12.2f} "
                  f"{posting_mb:<14} {forward_mb:<14} {total_mb:<12}")
        
        # Print detailed statistics
        print("\n" + "="*60)
        print("DETAILED STATISTICS")
        print("="*60)
        for r in successful:
            print(f"\n{r['dataset']} (alpha={r['alpha']}):")
            print(f"  Index path: {r['index_path']}")
            print(f"  Build time: {r['build_time_sec']:.2f} seconds")
            if r['total_documents'] is not None:
                print(f"  Total documents: {r['total_documents']:,}")
            if r['vocabulary_size'] is not None:
                print(f"  Vocabulary size: {r['vocabulary_size']:,}")
            if r['posting_list_mb'] is not None:
                print(f"  Posting list size: {r['posting_list_mb']:.2f} MB")
            if r['posting_list_nnz'] is not None:
                print(f"  Posting list non-zeros: {r['posting_list_nnz']:,}")
            if r['forward_index_mb'] is not None:
                print(f"  Forward index size: {r['forward_index_mb']:.2f} MB")
            if r['forward_index_nnz'] is not None:
                print(f"  Forward index non-zeros: {r['forward_index_nnz']:,}")
            if r['total_memory_mb'] is not None:
                print(f"  Total memory: {r['total_memory_mb']:.2f} MB")
    
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
        f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Thread count: {NUM_THREADS} (single-threaded benchmarking)\n\n")
        
        for r in results:
            f.write(f"Dataset: {r['dataset']}\n")
            f.write(f"Alpha: {r['alpha']}\n")
            f.write(f"Lambda: {r['lambda']}\n")
            f.write(f"Index Path: {r['index_path']}\n")
            f.write(f"Success: {r['success']}\n")
            
            if r['success']:
                f.write(f"Build Time: {r['build_time_sec']:.2f} seconds\n")
                f.write(f"Index File Size: {r['index_size_mb']:.2f} MB\n")
                
                if r.get('total_documents') is not None:
                    f.write(f"Total Documents: {r['total_documents']:,}\n")
                if r.get('vocabulary_size') is not None:
                    f.write(f"Vocabulary Size: {r['vocabulary_size']:,}\n")
                if r.get('posting_list_mb') is not None:
                    f.write(f"Posting List Size: {r['posting_list_mb']:.2f} MB\n")
                if r.get('posting_list_nnz') is not None:
                    f.write(f"Posting List Non-zeros: {r['posting_list_nnz']:,}\n")
                if r.get('forward_index_mb') is not None:
                    f.write(f"Forward Index Size: {r['forward_index_mb']:.2f} MB\n")
                if r.get('forward_index_nnz') is not None:
                    f.write(f"Forward Index Non-zeros: {r['forward_index_nnz']:,}\n")
                if r.get('total_memory_mb') is not None:
                    f.write(f"Total Memory: {r['total_memory_mb']:.2f} MB\n")
            
            f.write("\n")
    
    print(f"\nResults saved to: {results_file}")

if __name__ == "__main__":
    main()
