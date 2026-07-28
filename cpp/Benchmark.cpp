#include <iostream>
#include <iomanip>
#include <chrono>
#include <random>
#include <string>
#include "OrderBook.hpp"

using Clock = std::chrono::high_resolution_clock;

static const int WARMUP  =   100'000;
static const int MEASURE = 1'000'000;

// ------------------------------------------------------------------ //

void printResult(const std::string& label, int n, long long elapsedNs) {
    double nsPerOp    = (double)elapsedNs / n;
    double mOpsPerSec = n / (elapsedNs / 1e9) / 1'000'000.0;
    std::cout << std::left  << std::setw(26) << label
              << "  " << std::right << std::setw(9) << std::setprecision(0)
              << std::fixed << (double)n << " ops"
              << "   " << std::setw(6) << std::setprecision(1) << nsPerOp << " ns/op"
              << "   " << std::setw(5) << std::setprecision(2) << mOpsPerSec << " M ops/sec\n";
}

// ------------------------------------------------------------------ //
// Benchmark 1: submit() — add + match                                 //
// ------------------------------------------------------------------ //

void submitBenchmark(int n, bool print) {
    OrderBook book;
    std::mt19937 rng(42);
    std::normal_distribution<double> dist(5000.0, 3.0);
    std::uniform_int_distribution<int> sideDist(0, 1);

    // seed some depth so matches happen during measurement
    for (int i = 0; i < 500; i++) {
        int  price = std::max(1, (int)std::round(dist(rng)));
        Side side  = sideDist(rng) ? Side::BUY : Side::SELL;
        book.submit(new Order(side, price, 10));
    }

    auto start = Clock::now();
    for (int i = 0; i < n; i++) {
        int  price = std::max(1, (int)std::round(dist(rng)));
        Side side  = sideDist(rng) ? Side::BUY : Side::SELL;
        book.submit(new Order(side, price, 10));
    }
    auto elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(
                       Clock::now() - start).count();

    if (print) printResult("submit (add + match)", n, elapsed);
}

// ------------------------------------------------------------------ //
// Benchmark 2: cancelOrder() — O(1) lookup path                      //
// ------------------------------------------------------------------ //

void cancelBenchmark(int n, bool print) {
    OrderBook book;
    int mid = 5000;

    // pre-populate orders at non-crossing prices
    std::vector<long long> ids;
    ids.reserve(n);
    for (int i = 0; i < n; i++) {
        int  price = (i % 2 == 0) ? mid - 100 : mid + 100;
        Side side  = (i % 2 == 0) ? Side::BUY : Side::SELL;
        Order* o   = new Order(side, price, 10);
        book.addOrder(o);
        ids.push_back(o->orderId);
    }

    auto start = Clock::now();
    for (int i = 0; i < n; i++) {
        book.cancelOrder(ids[i]);
    }
    auto elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(
                       Clock::now() - start).count();

    if (print) printResult("cancel (O(1) lookup)", n, elapsed);
}

// ------------------------------------------------------------------ //

int main() {
    std::cout << "=== LOB C++ Benchmark ===\n\n";

    // warmup — JIT equivalent: let branch predictors and caches warm up
    submitBenchmark(WARMUP, false);
    cancelBenchmark(WARMUP, false);

    // measure
    submitBenchmark(MEASURE, true);
    cancelBenchmark(MEASURE, true);

    return 0;
}
