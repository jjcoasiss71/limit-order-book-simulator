// Case study: isolate the hash map as the single variable behind the cancel
// path. Same keys, same operations, only the map type differs.
//
//   std::unordered_map  — chained buckets, one heap node per entry
//   OrderMap            — flat open-addressing array (see OrderMap.hpp)
//
// This is the honest way to show the optimization: not by tuning one language's
// whole benchmark, but by measuring the one component that actually changed.

#include <iostream>
#include <iomanip>
#include <chrono>
#include <unordered_map>
#include <string>
#include "Order.hpp"
#include "OrderMap.hpp"

using Clock = std::chrono::high_resolution_clock;
static const long long N = 1'000'000;

template <typename F>
static long long timedNs(F f) {
    auto s = Clock::now();
    f();
    return std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - s).count();
}

static void row(const std::string& name, long long insNs, long long findNs) {
    auto mops = [](long long ns) { return N / (ns / 1e9) / 1e6; };
    std::cout << std::left  << std::setw(22) << name
              << std::right << std::fixed << std::setprecision(2)
              << std::setw(9)  << mops(insNs)  << " M/s (insert)"
              << std::setw(11) << mops(findNs) << " M/s (find+erase)\n";
}

// ------------------------------------------------------------------ //
// Correctness: prove the tombstone-reinsertion fix works.            //
// Force a collision, erase the earlier key, re-insert the later key, //
// and confirm no phantom duplicate survives.                          //
// ------------------------------------------------------------------ //

static void correctnessCheck() {
    OrderMap m;
    Order* a = new Order(Side::BUY, 1, 1);
    Order* b = new Order(Side::BUY, 2, 2);

    // two keys one CAP apart collide to the same start slot under identity hash
    long long k1 = 5;
    long long k2 = 5 + (1 << 21);   // k2 & MASK == k1 & MASK  → collision

    m.insert(k1, a);                 // k1 at slot 5
    m.insert(k2, b);                 // k2 probes to slot 6
    m.erase(k1);                     // slot 5 becomes a tombstone
    m.insert(k2, b);                 // must NOT create a second copy of k2

    bool ok = (m.size() == 1) && (m.find(k1) == nullptr) && (m.find(k2) != nullptr);
    std::cout << (ok ? "  PASS" : "  FAIL")
              << "  tombstone re-insertion (size=" << m.size() << ")\n\n";
    delete a; delete b;
}

// ------------------------------------------------------------------ //

int main() {
    std::cout << "=== Hash Map Case Study (1M sequential keys) ===\n\n";
    correctnessCheck();

    Order* dummy = new Order(Side::BUY, 5000, 10);
    volatile long long sink = 0;

    // ---- std::unordered_map ----
    long long su_ins, su_find;
    {
        std::unordered_map<long long, Order*> m;
        m.reserve(N * 2);
        su_ins = timedNs([&]{ for (long long k = 1; k <= N; ++k) m[k] = dummy; });
        su_find = timedNs([&]{
            for (long long k = 1; k <= N; ++k) {
                auto it = m.find(k);
                if (it != m.end()) { sink += (long long)it->second; m.erase(it); }
            }
        });
    }

    // ---- OrderMap (flat) ----
    long long om_ins, om_find;
    {
        OrderMap m;
        om_ins = timedNs([&]{ for (long long k = 1; k <= N; ++k) m.insert(k, dummy); });
        om_find = timedNs([&]{
            for (long long k = 1; k <= N; ++k) {
                Order** p = m.find(k);
                if (p) { sink += (long long)*p; m.erase(k); }
            }
        });
    }

    row("std::unordered_map", su_ins, su_find);
    row("OrderMap (flat)",    om_ins, om_find);

    std::cout << std::setprecision(1)
              << "\nspeed-up: insert "  << (double)su_ins  / om_ins  << "x"
              << "   find+erase "       << (double)su_find / om_find << "x\n";

    (void)sink;
    delete dummy;
    return 0;
}
