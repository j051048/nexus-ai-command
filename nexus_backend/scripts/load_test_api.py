import asyncio
import time
import httpx
import statistics
import collections
import sys

async def fetch(client, url):
    start = time.perf_counter()
    try:
        resp = await client.get(url)
        # 模拟读取响应体，测试 TTFT 之后的传输耗时
        await resp.aread()
        latency = time.perf_counter() - start
        return resp.status_code, latency
    except Exception as e:
        latency = time.perf_counter() - start
        return str(type(e).__name__), latency

async def load_test(url, concurrency, total_requests):
    print(f"==================================================")
    print(f"🚀 [性能 & 压力测试] 启动高并发接口压测...")
    print(f"🎯 目标端点: {url}")
    print(f"⚡ 模拟用户并发数 (Concurrency): {concurrency}")
    print(f"📦 总发包次数 (Total Requests): {total_requests}")
    print(f"==================================================\n")
    
    timeout = httpx.Timeout(10.0)
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    
    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        # Warmup (预热建立连接)
        try:
            await client.get(url)
            print("⏳ 预热请求成功，连接池已建立，开始并发打击...\n")
        except Exception as e:
            print(f"❌ [错误] 预热请求失败: {e}，请检查目标服务是否已启动。")
            return
            
        start_time = time.perf_counter()
        sem = asyncio.Semaphore(concurrency)
        
        async def bounded_fetch():
            async with sem:
                return await fetch(client, url)
                
        tasks = [bounded_fetch() for _ in range(total_requests)]
        results = await asyncio.gather(*tasks)
        
        total_time = time.perf_counter() - start_time
        
        status_codes = [r[0] for r in results]
        latencies = [r[1] for r in results]
        
        print("-" * 50)
        print("📊 压测结果分析报告 (Load Test Report)")
        print("-" * 50)
        print(f"总请求完成数          : {total_requests}")
        print(f"线程并发度            : {concurrency}")
        print(f"总测试耗时            : {total_time:.3f} 秒")
        print(f"🏆 吞吐量 (QPS)       : {total_requests / total_time:.2f} req/s")
        
        print("\n⏱ 延迟与首Token统计 (Latency Metrics):")
        print(f"  最短响应时间 (Min)   : {min(latencies)*1000:.2f} ms")
        print(f"  最长响应时间 (Max)   : {max(latencies)*1000:.2f} ms")
        print(f"  平均响应时间 (Mean)  : {statistics.mean(latencies)*1000:.2f} ms")
        if len(latencies) >= 2:
            print(f"  中位数 (Median)      : {statistics.median(latencies)*1000:.2f} ms")
            if len(latencies) >= 10:
                p95 = statistics.quantiles(latencies, n=100)[94]
                p99 = statistics.quantiles(latencies, n=100)[98]
                print(f"  🔥 95分位 (P95)      : {p95*1000:.2f} ms")
                print(f"  🚨 99分位 (P99)      : {p99*1000:.2f} ms")
        
        print("\n📈 状态码与熔断情况 (Status Codes Distribution):")
        counter = collections.Counter(status_codes)
        for code, count in counter.items():
            if str(code) == "200":
                print(f"  ✅ HTTP {code}: {count} 次 (占比 {count/total_requests*100:.1f}%)")
            else:
                print(f"  ❌ {code}: {count} 次 (占比 {count/total_requests*100:.1f}%)")

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8123/health"
    concurrency = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    total = int(sys.argv[3]) if len(sys.argv) > 3 else 1000
    
    asyncio.run(load_test(url, concurrency, total))
