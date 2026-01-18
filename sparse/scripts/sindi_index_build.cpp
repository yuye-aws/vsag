#include <omp.h>
#include <sys/stat.h>
#include <chrono>
#include <cstring>
#include <fstream>
#include <iostream>
#include <iomanip>
#include <nlohmann/json.hpp>
#include <getopt.h>
#include <unordered_set>

#include "vsag/vsag.h"

using namespace std::chrono;

struct MemoryStats {
    size_t posting_list_memory = 0;
    size_t forward_index_memory = 0;
    size_t header_memory = 0;
    uint32_t total_count = 0;
    uint32_t data_dim = 0;
    uint32_t lambda = 0;
    uint32_t sigma = 0;
    size_t posting_list_nnz = 0;
    size_t forward_index_nnz = 0;
    uint32_t non_empty_lists = 0;
};

MemoryStats calculate_memory_from_index(const std::string& index_path) {
    MemoryStats stats;
    
    std::ifstream f(index_path, std::ios::binary);
    if (!f) {
        std::cerr << "Error: Cannot open index file for memory calculation" << std::endl;
        return stats;
    }
    
    // Read header (4 uint32_t values)
    f.read(reinterpret_cast<char*>(&stats.total_count), sizeof(uint32_t));
    f.read(reinterpret_cast<char*>(&stats.data_dim), sizeof(uint32_t));
    f.read(reinterpret_cast<char*>(&stats.lambda), sizeof(uint32_t));
    f.read(reinterpret_cast<char*>(&stats.sigma), sizeof(uint32_t));
    
    stats.header_memory = 4 * sizeof(uint32_t);
    
    // Calculate posting list memory
    for (uint32_t i = 0; i < stats.data_dim; ++i) {
        uint32_t doc_num;
        f.read(reinterpret_cast<char*>(&doc_num), sizeof(uint32_t));
        stats.posting_list_memory += sizeof(uint32_t); // doc_num field
        
        if (doc_num > 0) {
            stats.non_empty_lists++;
            // Skip ids, vals, and offsets
            f.seekg(doc_num * sizeof(uint32_t), std::ios::cur); // ids
            f.seekg(doc_num * sizeof(float), std::ios::cur);    // vals
            f.seekg((stats.sigma + 1) * sizeof(uint32_t), std::ios::cur); // offsets
            
            // Calculate memory
            stats.posting_list_memory += doc_num * sizeof(uint32_t); // ids
            stats.posting_list_memory += doc_num * sizeof(float);    // vals
            stats.posting_list_memory += (stats.sigma + 1) * sizeof(uint32_t); // offsets
            stats.posting_list_nnz += doc_num;
        }
    }
    
    // Calculate forward index memory
    for (uint32_t doc_id = 0; doc_id < stats.total_count; ++doc_id) {
        uint32_t dim;
        f.read(reinterpret_cast<char*>(&dim), sizeof(uint32_t));
        stats.forward_index_memory += sizeof(uint32_t); // dim field
        
        if (dim > 0) {
            // Skip ids and vals
            f.seekg(dim * sizeof(uint32_t), std::ios::cur); // ids
            f.seekg(dim * sizeof(float), std::ios::cur);    // vals
            
            // Calculate memory
            stats.forward_index_memory += dim * sizeof(uint32_t); // ids
            stats.forward_index_memory += dim * sizeof(float);    // vals
            stats.forward_index_nnz += dim;
        }
    }
    
    f.close();
    return stats;
}

void print_memory_stats(const MemoryStats& stats, double build_time_sec) {
    std::cout << "\n" << std::string(70, '=') << "\n";
    std::cout << "SINDI INDEX BUILD STATISTICS\n";
    std::cout << std::string(70, '=') << "\n";
    
    std::cout << "\nIndex Parameters:\n";
    std::cout << "  Total documents: " << stats.total_count << "\n";
    std::cout << "  Vocabulary size: " << stats.data_dim << "\n";
    std::cout << "  Lambda (window size): " << stats.lambda << "\n";
    std::cout << "  Sigma (num windows): " << stats.sigma << "\n";
    std::cout << "  Build time: " << std::fixed << std::setprecision(2) << build_time_sec << " seconds\n";
    
    std::cout << "\n" << std::string(70, '-') << "\n";
    std::cout << "POSTING LIST (Inverted Index) MEMORY\n";
    std::cout << std::string(70, '-') << "\n";
    std::cout << "  Memory: " << std::fixed << std::setprecision(2) 
              << stats.posting_list_memory / (1024.0 * 1024.0) << " MB ("
              << stats.posting_list_memory << " bytes)\n";
    std::cout << "  Non-empty lists: " << stats.non_empty_lists << " / " 
              << stats.data_dim << " (" << std::fixed << std::setprecision(1)
              << (stats.non_empty_lists * 100.0 / stats.data_dim) << "%)\n";
    std::cout << "  Total non-zeros: " << stats.posting_list_nnz << "\n";
    if (stats.non_empty_lists > 0) {
        std::cout << "  Avg per non-empty list: " << std::fixed << std::setprecision(2)
                  << (stats.posting_list_nnz * 1.0 / stats.non_empty_lists) << "\n";
    }
    std::cout << "  Avg per document: " << std::fixed << std::setprecision(2)
              << (stats.posting_list_nnz * 1.0 / stats.total_count) << "\n";
    
    std::cout << "\n" << std::string(70, '-') << "\n";
    std::cout << "FORWARD INDEX MEMORY\n";
    std::cout << std::string(70, '-') << "\n";
    std::cout << "  Memory: " << std::fixed << std::setprecision(2)
              << stats.forward_index_memory / (1024.0 * 1024.0) << " MB ("
              << stats.forward_index_memory << " bytes)\n";
    std::cout << "  Total non-zeros: " << stats.forward_index_nnz << "\n";
    std::cout << "  Avg per document: " << std::fixed << std::setprecision(2)
              << (stats.forward_index_nnz * 1.0 / stats.total_count) << "\n";
    
    size_t total_memory = stats.header_memory + stats.posting_list_memory + stats.forward_index_memory;
    std::cout << "\n" << std::string(70, '-') << "\n";
    std::cout << "TOTAL MEMORY\n";
    std::cout << std::string(70, '-') << "\n";
    std::cout << "  Header: " << std::fixed << std::setprecision(2)
              << stats.header_memory / 1024.0 << " KB\n";
    std::cout << "  Posting lists: " << std::fixed << std::setprecision(2)
              << stats.posting_list_memory / (1024.0 * 1024.0) << " MB ("
              << std::fixed << std::setprecision(1)
              << (stats.posting_list_memory * 100.0 / total_memory) << "%)\n";
    std::cout << "  Forward index: " << std::fixed << std::setprecision(2)
              << stats.forward_index_memory / (1024.0 * 1024.0) << " MB ("
              << std::fixed << std::setprecision(1)
              << (stats.forward_index_memory * 100.0 / total_memory) << "%)\n";
    std::cout << "  Total: " << std::fixed << std::setprecision(2)
              << total_memory / (1024.0 * 1024.0) << " MB ("
              << total_memory << " bytes)\n";
    
    std::cout << std::string(70, '=') << "\n";
}

std::pair<vsag::SparseVector*, int64_t>
read_sparse_vectors_from_csr_file(const std::string& filename) {
    std::ifstream infile(filename, std::ios::binary);
    if (!infile) {
        throw std::runtime_error("Could not open file");
    }

    int64_t sizes[3];
    infile.read(reinterpret_cast<char*>(sizes), 3 * sizeof(int64_t));
    int64_t num_rows = sizes[0];
    int64_t num_cols = sizes[1];
    int64_t nnz = sizes[2];

    std::vector<int64_t> indptr(num_rows + 1);
    infile.read(reinterpret_cast<char*>(indptr.data()), (num_rows + 1) * sizeof(int64_t));

    std::vector<int32_t> indices(nnz);
    infile.read(reinterpret_cast<char*>(indices.data()), nnz * sizeof(int32_t));

    std::vector<float> data(nnz);
    infile.read(reinterpret_cast<char*>(data.data()), nnz * sizeof(float));

    infile.close();

    vsag::SparseVector* sparse_vectors = new vsag::SparseVector[num_rows];

    for (int64_t i = 0; i < num_rows; ++i) {
        int64_t row_start = indptr[i];
        int64_t row_end = indptr[i + 1];
        int64_t row_size = row_end - row_start;

        sparse_vectors[i].dim_ = static_cast<uint32_t>(row_size);
        sparse_vectors[i].ids_ = new uint32_t[row_size];
        sparse_vectors[i].vals_ = new float[row_size];

        std::memcpy(
            sparse_vectors[i].ids_, indices.data() + row_start, row_size * sizeof(uint32_t));
        std::memcpy(sparse_vectors[i].vals_, data.data() + row_start, row_size * sizeof(float));
    }
    return std::make_pair(sparse_vectors, num_rows);
}

int main(int argc, char** argv) {
    if (argc < 5 || argc > 6) {
        std::cerr << "Usage: " << argv[0]
                  << " <basefile> <lambda> <alpha> <index_path> [num_threads]\n";
        std::cerr << "  num_threads: optional, defaults to 1 (use 0 for max available threads)\n";
        return 1;
    }

    std::string basefile = argv[1];
    int lambda = std::stoi(argv[2]);
    float alpha = std::stof(argv[3]);
    std::string index_path = argv[4];
    int num_threads = (argc == 6) ? std::stoi(argv[5]) : 1;
    
    // Set thread count (0 means use all available threads)
    if (num_threads == 0) {
        num_threads = omp_get_max_threads();
    }

    std::cout << "basefile: " << basefile << "\n";
    std::cout << "lambda: " << lambda << "\n";
    std::cout << "alpha: " << alpha << "\n";
    std::cout << "index_path: " << index_path << "\n";
    std::cout << "num_threads: " << num_threads << "\n";

    std::pair<vsag::SparseVector*, int64_t> base_results = read_sparse_vectors_from_csr_file(basefile);
    
    auto base = vsag::Dataset::Make();
    base->SparseVectors(base_results.first)->NumElements(base_results.second)->Owner(true);
    
    vsag::init();
    nlohmann::json sindi_build_parameters = {
            {"dtype", "float32"},
            {"metric_type", "ip"},
            {"dim", 30000},
            {"sindi",
             {{"lambda", lambda},
              {"alpha", alpha},
              {"prune_stragy", "MassRatio"}}}};

    std::cout << "\nStart building sindi index with " << num_threads << " thread(s)" << std::endl;
    
    // Set number of threads for index building
    omp_set_num_threads(num_threads);
    
    auto index =
        vsag::Factory::CreateIndex("sindi", sindi_build_parameters.dump()).value();

    // Measure build time
    auto build_start = high_resolution_clock::now();
    
    if (auto build_result = index->Build(base); build_result.has_value()) {
        auto build_end = high_resolution_clock::now();
        auto build_duration = duration_cast<milliseconds>(build_end - build_start);
        double build_time_sec = build_duration.count() / 1000.0;
        
        std::cout << "Build completed successfully" << std::endl;
        std::cout << "Number of vectors indexed: " << index->GetNumElements() << std::endl;
        
        // Serialize index
        std::ofstream index_file(index_path, std::ios::binary);
        if (!index_file) {
            std::cerr << "Error opening file for serialization." << std::endl;
            return 1;
        }
        index->Serialize(index_file);
        index_file.close();
        
        // Calculate and print memory statistics
        MemoryStats stats = calculate_memory_from_index(index_path);
        print_memory_stats(stats, build_time_sec);
        
    } else if (build_result.error().type == vsag::ErrorType::INTERNAL_ERROR) {
        std::cerr << "Failed to build index: internalError" << std::endl;
        exit(-1);
    }

    return 0;
}