import cProfile
import pstats
import sys
from datetime import datetime
from src.screener import run_all_scanners

def profile_scan():
    profiler = cProfile.Profile()
    profiler.enable()
    
    start = datetime.now()
    results = run_all_scanners()  # full production scan
    elapsed = (datetime.now() - start).total_seconds()
    
    profiler.disable()
    
    # Save stats
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumtime')
    stats.dump_stats('scan_profile.prof')
    
    print(f"Total scan time: {elapsed:.2f}s")
    print(f"Symbols scanned: {len(results)}")
    print("Top 20 time sinks:")
    stats.print_stats(20)
    
    return results

if __name__ == "__main__":
    profile_scan()
