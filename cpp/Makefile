CXX      = g++
CXXFLAGS = -std=c++17 -O3 -Wall -Wextra

all: test benchmark

test: OrderBook.cpp Test.cpp Order.hpp OrderBook.hpp
	$(CXX) $(CXXFLAGS) OrderBook.cpp Test.cpp -o test

benchmark: OrderBook.cpp Benchmark.cpp Order.hpp OrderBook.hpp
	$(CXX) $(CXXFLAGS) OrderBook.cpp Benchmark.cpp -o benchmark

clean:
	rm -f test benchmark
