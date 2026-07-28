#include "OrderBook.hpp"
#include <algorithm>

// ------------------------------------------------------------------ //
// Public interface                                                     //
// ------------------------------------------------------------------ //

void OrderBook::addOrder(Order* order) {
    orders[order->orderId] = order;
    if (order->side == Side::BUY)
        bids[order->price].push_back(order);
    else
        asks[order->price].push_back(order);
}

void OrderBook::submit(Order* order) {
    if (order->side == Side::BUY) matchBuy(order);
    else                          matchSell(order);

    if (order->quantity > 0) addOrder(order);   // rest the remainder
    else                     delete order;       // fully filled — no GC, we delete
}

bool OrderBook::cancelOrder(long long orderId) {
    auto it = orders.find(orderId);
    if (it == orders.end()) return false;

    Order* order = it->second;
    orders.erase(it);

    // remove from the correct side's price level
    if (order->side == Side::BUY) {
        auto& level = bids[order->price];
        level.erase(std::find(level.begin(), level.end(), order));
        if (level.empty()) bids.erase(order->price);
    } else {
        auto& level = asks[order->price];
        level.erase(std::find(level.begin(), level.end(), order));
        if (level.empty()) asks.erase(order->price);
    }

    delete order;
    return true;
}


// ------------------------------------------------------------------ //
// Matching engine                                                      //
// ------------------------------------------------------------------ //

void OrderBook::matchBuy(Order* order) {
    while (order->quantity > 0 && !asks.empty()) {
        auto it = asks.begin();              // lowest ask price
        if (order->price < it->first) break; // can't afford — stop

        auto&   level   = it->second;
        Order*  resting = level.front();     // front of FIFO queue

        int fill = std::min(order->quantity, resting->quantity);
        order->quantity   -= fill;
        resting->quantity -= fill;
        recordTrade(it->first, fill);

        if (resting->quantity == 0) {
            level.pop_front();
            orders.erase(resting->orderId);
            delete resting;
            if (level.empty()) asks.erase(it);
        }
    }
}

void OrderBook::matchSell(Order* order) {
    while (order->quantity > 0 && !bids.empty()) {
        auto it = bids.begin();              // highest bid (std::greater)
        if (order->price > it->first) break; // price too high — stop

        auto&   level   = it->second;
        Order*  resting = level.front();

        int fill = std::min(order->quantity, resting->quantity);
        order->quantity   -= fill;
        resting->quantity -= fill;
        recordTrade(it->first, fill);

        if (resting->quantity == 0) {
            level.pop_front();
            orders.erase(resting->orderId);
            delete resting;
            if (level.empty()) bids.erase(it);
        }
    }
}

void OrderBook::recordTrade(int price, int quantity) {
    trades.push_back({(long long)price, (long long)quantity});
}
