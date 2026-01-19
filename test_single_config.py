#!/usr/bin/env python3
"""
Test a single SINDI search configuration
Quick utility to test specific beta/gamma values
"""

import subprocess
import sys
import re

# Configuration
SEARCH_BIN = "/home/ec2-user/Code/vsag/build-release/sparse/scripts/sindi_index_search"
INDEX_PATH = "msmarco_v1_sindi_no_prune.index"
QUERIES_CSR = "/home/ec2-user/sparse_datasets/msmarco_v1_cocondenser/queries.csr"
GT_FILE = "msmarco_v1_gt.bin"
TOPK = 10
NUM_THREADS = 1

def test_config(beta, gamma, index_path=INDEX_PATH):
    """Test a single configuration"""
    
    cmd = [
        SEARCH_BIN,
        index_path,
        QUERIES_CSR,
        GT_FILE,
        str(beta),
        str(gamma),
        str(TOPK),
        str(NUM_THREADS)
    ]
    
    print("="*60)
    print(f"Testing Configuration")
    print("="*60)
    print(f"Index: {index_path}")
    print(f"Beta: {beta}")
    print(f"Gamma: {gamma}")
    print(f"Top-K: {TOPK}")
    print(f"Threads: {NUM_THREADS}")
    print()
    print(f"Command: {' '.join(cmd)}")
    print("="*60)
    print()
    
    try:
        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=300
        )
        
        output = result.stdout
        print(output)
        
        # Parse and highlight key metrics
        recall_match = re.search(r'recall[:\s]+([0-9.]+)', output, re.IGNORECASE)
        qps_match = re.search(r'qps[:\s]+([0-9.]+)', output, re.IGNORECASE)
        
        if recall_match and qps_match:
            recall = float(recall_match.group(1))
            qps = float(qps_match.group(1))
            
            print("="*60)
            print("RESULTS SUMMARY")
            print("="*60)
            print(f"Recall: {recall*100:.2f}%")
            print(f"QPS: {qps:.2f}")
            print("="*60)
            
            return recall, qps
        
    except subprocess.CalledProcessError as e:
        print(f"Error running search: {e}")
        print(e.stdout)
        return None, None
    except subprocess.TimeoutExpired:
        print("Error: Search timed out (>5 minutes)")
        return None, None

def main():
    if len(sys.argv) < 3:
        print("Usage: python test_single_config.py <beta> <gamma> [index_path]")
        print()
        print("Examples:")
        print("  python test_single_config.py 0.5 200")
        print("  python test_single_config.py 0.7 800")
        print("  python test_single_config.py 1.0 1500 msmarco_v1_sindi_alpha_0.3.index")
        sys.exit(1)
    
    beta = float(sys.argv[1])
    gamma = int(sys.argv[2])
    index_path = sys.argv[3] if len(sys.argv) > 3 else INDEX_PATH
    
    test_config(beta, gamma, index_path)

if __name__ == "__main__":
    main()
