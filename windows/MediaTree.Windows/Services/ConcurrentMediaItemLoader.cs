using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;

namespace MediaTree.Windows.Services;

public static class ConcurrentMediaItemLoader
{
    public const int DefaultMaxConcurrency = 6;

    public static async Task<List<TResult>> MapAsync<TSource, TResult>(
        IReadOnlyList<TSource> items,
        int maxConcurrency,
        Func<TSource, CancellationToken, Task<TResult>> loadAsync,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(items);
        ArgumentNullException.ThrowIfNull(loadAsync);
        if (items.Count == 0)
        {
            return [];
        }

        var concurrency = Math.Clamp(maxConcurrency, 1, items.Count);
        var results = new TResult[items.Count];
        var nextIndex = -1;
        var workers = Enumerable.Range(0, concurrency)
            .Select(_ => RunWorkerAsync())
            .ToArray();

        await Task.WhenAll(workers);
        return results.ToList();

        async Task RunWorkerAsync()
        {
            while (true)
            {
                var index = Interlocked.Increment(ref nextIndex);
                if (index >= items.Count)
                {
                    return;
                }

                cancellationToken.ThrowIfCancellationRequested();
                results[index] = await loadAsync(items[index], cancellationToken);
            }
        }
    }
}
