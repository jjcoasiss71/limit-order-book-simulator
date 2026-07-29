CXX      = g++
CXXFLAGS = -std=c++17 -O3 -Wall -Wextra

all: test benchmark mapbench

test: OrderBook.cpp Test.cpp Order.hpp OrderBook.hpp
	$(CXX) $(CXXFLAGS) OrderBook.cpp Test.cpp -o test

benchmark: OrderBook.cpp Benchmark.cpp Order.hpp OrderBook.hpp
	$(CXX) $(CXXFLAGS) OrderBook.cpp Benchmark.cpp -o benchmark

# Case study: std::unordered_map vs flat OrderMap, in isolation
mapbench: MapBenchmark.cpp Order.hpp OrderMap.hpp
	$(CXX) $(CXXFLAGS) MapBenchmark.cpp -o mapbench

clean:
	rm -f test benchmark mapbench
