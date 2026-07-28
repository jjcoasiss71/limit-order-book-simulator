#include <iostream>
#include <string>
#include "OrderBook.hpp"

static int passed = 0, failed = 0;

void check(const std::string& label, int expected, int actual) {
    if (expected == actual) {
        std::cout << "  PASS  " << label << "\n";
        ++passed;
    } else {
        std::cout << "  FAIL  " << label
                  << " — expected " << expected << ", got " << actual << "\n";
        ++failed;
    }
}

// ------------------------------------------------------------------ //
// Same 6 scenarios as Java Test.java                                  //
// ------------------------------------------------------------------ //

void test1_basicMatch() {
    OrderBook book;
    book.addOrder(new Order(Side::SELL, 5001, 100));
    book.submit(  new Order(Side::BUY,  5001, 100));

    check("test1 trades",      1,    book.tradeCount());
    check("test1 trade price", 5001, (int)book.trades[0][0]);
    check("test1 trade qty",   100,  (int)book.trades[0][1]);
    check("test1 orders left", 0,    book.orderCount());
    check("test1 bestAsk",     -1,   book.bestAsk());
}

void test2_partialFill() {
    OrderBook book;
    book.addOrder(new Order(Side::SELL, 5001, 50));
    book.submit(  new Order(Side::BUY,  5001, 100));

    check("test2 trades",      1,    book.tradeCount());
    check("test2 trade qty",   50,   (int)book.trades[0][1]);
    check("test2 orders left", 1,    book.orderCount());
    check("test2 bestBid",     5001, book.bestBid());
    check("test2 bestAsk",     -1,   book.bestAsk());
}

void test3_noMatch() {
    OrderBook book;
    book.submit(new Order(Side::BUY,  5000, 100));
    book.submit(new Order(Side::SELL, 5002, 100));

    check("test3 trades",   0,    book.tradeCount());
    check("test3 bestBid",  5000, book.bestBid());
    check("test3 bestAsk",  5002, book.bestAsk());
    check("test3 orders",   2,    book.orderCount());
}

void test4_cancel() {
    OrderBook book;
    Order* o = new Order(Side::BUY, 5000, 100);
    book.addOrder(o);
    check("test4 before cancel", 1, book.orderCount());

    check("test4 cancel ok",   1, book.cancelOrder(o->orderId) ? 1 : 0);
    check("test4 after cancel", 0, book.orderCount());
    check("test4 bestBid",     -1, book.bestBid());

    // o is deleted by cancelOrder — double cancel must return false
    check("test4 double cancel", 0, book.cancelOrder(1) ? 1 : 0);
}

void test5_fifo() {
    OrderBook book;
    Order* first  = new Order(Side::BUY, 5000, 50);
    Order* second = new Order(Side::BUY, 5000, 50);
    book.addOrder(first);
    book.addOrder(second);

    book.submit(new Order(Side::SELL, 5000, 50));

    check("test5 first filled",  0,  first->quantity);
    check("test5 second intact", 50, second->quantity);
    check("test5 orders left",   1,  book.orderCount());
}

void test6_multiLevelSweep() {
    OrderBook book;
    book.addOrder(new Order(Side::SELL, 5001, 30));
    book.addOrder(new Order(Side::SELL, 5002, 30));

    book.submit(new Order(Side::BUY, 5005, 80));

    check("test6 trades",      2,    book.tradeCount());
    check("test6 asks empty",  -1,   book.bestAsk());
    check("test6 bid resting", 5005, book.bestBid());
}

// ------------------------------------------------------------------ //

int main() {
    test1_basicMatch();
    test2_partialFill();
    test3_noMatch();
    test4_cancel();
    test5_fifo();
    test6_multiLevelSweep();

    std::cout << "\n" << passed << " passed, " << failed << " failed\n";
    return failed > 0 ? 1 : 0;
}
