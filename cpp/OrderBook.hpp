#pragma once
#include <map>
#include <deque>
#include <unordered_map>
#include <vector>
#include <array>
#include <functional>
#include "Order.hpp"

class OrderBook {
public:
    // std::greater<int> flips TreeMap ordering — highest price = begin()
    // same as Java's new TreeMap<>(Comparator.reverseOrder())
    std::map<int, std::deque<Order*>, std::greater<int>> bids;
    std::map<int, std::deque<Order*>>                    asks;

    // O(1) lookup by order ID — same as Java's HashMap
    std::unordered_map<long long, Order*>                orders;

    // trade log: each entry is {price, quantity}
    std::vector<std::array<long long, 2>>                trades;

    void addOrder(Order* order);   // rest without matching (ITCH replay path)
    void submit(Order* order);     // match first, rest remainder
    bool cancelOrder(long long orderId);

    // -1 = empty (sentinel instead of Java's null / Python's None)
    int bestBid()    const { return bids.empty()   ? -1 : bids.begin()->first; }
    int bestAsk()    const { return asks.empty()   ? -1 : asks.begin()->first; }
    int orderCount() const { return (int)orders.size(); }
    int tradeCount() const { return (int)trades.size(); }

private:
    void matchBuy(Order* order);
    void matchSell(Order* order);
    void recordTrade(int price, int quantity);
};
