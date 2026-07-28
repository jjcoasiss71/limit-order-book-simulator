#pragma once
#include <chrono>

// enum class = scoped enum — must write Side::BUY, not just BUY
enum class Side { BUY, SELL };

struct Order {
    // inline static = class-level counter, defined here (C++17)
    // same role as Java's `private static long nextId = 1`
    inline static long long nextId = 1;

    long long orderId;
    Side      side;
    int       price;      // ticks — same convention as Python and Java
    int       quantity;   // mutable: shrinks on partial fill
    long long timestamp;  // nanoseconds — same as Java's System.nanoTime()

    Order(Side side, int price, int quantity)
        : orderId(nextId++),
          side(side),
          price(price),
          quantity(quantity),
          timestamp(std::chrono::high_resolution_clock::now().time_since_epoch().count())
    {}
};
