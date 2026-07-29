#pragma once
#include <vector>
#include <cassert>
#include "Order.hpp"

// ------------------------------------------------------------------ //
// Flat open-addressing hash map — a case study, NOT the default book. //
// ------------------------------------------------------------------ //
//
// std::unordered_map uses separate chaining: each bucket is a linked list of
// individually heap-allocated nodes. Every lookup follows a pointer to a random
// heap address → a cache miss on nearly every call. That is why the fair
// benchmark shows C++ losing the cancel path to Java's HashMap.
//
// This map lays every slot in one contiguous array and resolves collisions with
// linear probing, so a miss pulls the next probe slot into the same cache line.
//
// SCOPE / LIMITATIONS (honest caveats):
//   * Fixed capacity, no rehash — sized once for the benchmark. Overflow is
//     caught by an assert rather than silently looping.
//   * Identity hash (key & MASK) is chosen because the engine feeds it dense
//     sequential IDs (1, 2, 3, …). Sparse keys — e.g. NASDAQ order references
//     from the ITCH parser — would need a real hash (multiplicative/Fibonacci).
//   * The same speed-up is available to Java via primitive-keyed maps
//     (Agrona Long2ObjectHashMap) — this is a layout win, not a language win.

class OrderMap {
    static constexpr size_t    CAP     = 1 << 21;   // 2M slots = 32 MB
    static constexpr size_t    MASK    = CAP - 1;
    static constexpr size_t    MAX_LOAD = (CAP * 3) / 4;  // guard against overflow
    static constexpr long long EMPTY   =  0;         // 0 is never a valid order ID
    static constexpr long long DELETED = -1;         // tombstone for erased slots

    struct Slot { long long key = EMPTY; Order* value = nullptr; };

    std::vector<Slot> table;
    size_t count_ = 0;

    // Identity hash: dense sequential IDs land in adjacent slots, so a cache
    // line (4 slots) covers four consecutive IDs — sequential access stays warm.
    static size_t probe(long long key) {
        return (size_t)key & MASK;
    }

public:
    OrderMap() : table(CAP) {}

    void insert(long long key, Order* value) {
        assert(count_ < MAX_LOAD && "OrderMap capacity exceeded — increase CAP");
        size_t i = probe(key);
        size_t firstTomb = CAP;                 // CAP = "no tombstone seen yet"
        // scan the full probe chain to EMPTY to confirm the key isn't already
        // present further down; reuse the earliest tombstone if one exists.
        while (table[i].key != EMPTY) {
            if (table[i].key == key) {          // key already here — update in place
                table[i].value = value;
                return;
            }
            if (table[i].key == DELETED && firstTomb == CAP) firstTomb = i;
            i = (i + 1) & MASK;
        }
        size_t dst = (firstTomb != CAP) ? firstTomb : i;
        table[dst] = {key, value};
        ++count_;
    }

    // Returns a pointer to the stored Order*, or nullptr if not found.
    Order** find(long long key) {
        size_t i = probe(key);
        while (table[i].key != EMPTY) {         // DELETED slots are skipped, not stopped on
            if (table[i].key == key) return &table[i].value;
            i = (i + 1) & MASK;
        }
        return nullptr;
    }

    bool erase(long long key) {
        size_t i = probe(key);
        while (table[i].key != EMPTY) {
            if (table[i].key == key) {
                table[i] = {DELETED, nullptr};
                --count_;
                return true;
            }
            i = (i + 1) & MASK;
        }
        return false;
    }

    size_t size() const { return count_; }
};
