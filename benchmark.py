import time
import urllib.request
import urllib.error
import statistics
import json

# Konfigurasi
BASE_URL = "http://localhost:8000/api/v1"
ITERATIONS = 100

def run_benchmark(endpoint, name):
    url = f"{BASE_URL}{endpoint}"
    print(f"\n--- Benchmarking {name} ({ITERATIONS} requests) ---")
    print(f"URL: {url}")
    
    # Warmup request
    try:
        req = urllib.request.Request(url, headers={'X-Benchmark': 'true'})
        urllib.request.urlopen(req)
    except urllib.error.URLError as e:
        print(f"Error: Tidak dapat terhubung ke server. {e}")
        return

    times = []
    
    for i in range(ITERATIONS):
        start_time = time.time()
        try:
            req = urllib.request.Request(url, headers={'X-Benchmark': 'true'})
            response = urllib.request.urlopen(req)
            end_time = time.time()
            if response.getcode() != 200:
                print(f"Error pada iterasi {i}: Status {response.getcode()}")
                break
            times.append((end_time - start_time) * 1000)  # dalam milidetik
        except urllib.error.HTTPError as e:
            print(f"HTTP Error pada iterasi {i}: Status {e.code}")
            break

    if times:
        avg_time = statistics.mean(times)
        min_time = min(times)
        max_time = max(times)
        p95 = statistics.quantiles(times, n=100)[94] if len(times) >= 2 else max_time
        
        print(f"Total Requests: {len(times)}")
        print(f"Rata-rata   : {avg_time:.2f} ms")
        print(f"Minimum     : {min_time:.2f} ms")
        print(f"Maksimum    : {max_time:.2f} ms")
        print(f"Percentile 95: {p95:.2f} ms")

if __name__ == "__main__":
    print("Mulai Benchmark Simple LMS API...")
    
    # Endpoint yang tidak di-cache (menggunakan filter akan bypass cache sesuai logic kita)
    run_benchmark("/courses/?search=Python", "Course List (Uncached / Filtered)")
    
    # Endpoint yang di-cache
    run_benchmark("/courses/", "Course List (Cached)")
    
    # Course popular (redis sorted set)
    run_benchmark("/courses/popular/", "Popular Courses (Redis Sorted Set)")
