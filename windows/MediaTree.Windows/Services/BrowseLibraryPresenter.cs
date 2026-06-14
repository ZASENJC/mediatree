using System;
using System.Collections.Generic;
using System.Linq;
using MediaTree.Windows.Models;

namespace MediaTree.Windows.Services;

public static class BrowseLibraryPresenter
{
    public static IReadOnlyList<MediaRootDto> DistinctMediaRoots(IEnumerable<MediaRootDto> roots)
    {
        var result = new List<MediaRootDto>();
        foreach (var root in roots)
        {
            if (string.IsNullOrWhiteSpace(root.Path))
            {
                continue;
            }

            if (result.Any(existing => LibraryService.RootsMatch(existing.Path, root.Path)))
            {
                continue;
            }

            result.Add(root);
        }

        return result;
    }

    public static IReadOnlyList<string> ActiveMediaRootPaths(IEnumerable<MediaRootDto> roots)
        => DistinctMediaRoots(roots).Select(root => root.Path).ToList();

    public static MoviesResponseDto MergeMovieResponses(
        IEnumerable<MoviesResponseDto> responses,
        string sort,
        int limit,
        int offset = 0)
    {
        var responseList = responses.ToList();
        var movies = responseList.SelectMany(response => response.Movies);
        return new MoviesResponseDto
        {
            Movies = SortMovies(movies, sort)
                .Skip(Math.Max(0, offset))
                .Take(Math.Max(0, limit))
                .ToList(),
            Total = responseList.Sum(response => response.Total),
        };
    }

    public static MoviesResponseDto FilterExcludedMovies(
        MoviesResponseDto response,
        IEnumerable<string> excludedFolders,
        bool preserveTotal = false)
    {
        var excluded = excludedFolders
            .Select(NormalizeFolderPath)
            .Where(path => !string.IsNullOrWhiteSpace(path))
            .ToList();
        if (excluded.Count == 0)
        {
            return response;
        }

        var movies = response.Movies
            .Where(movie => !IsFolderPathExcluded(movie.FolderForSpecials, excluded))
            .ToList();
        return new MoviesResponseDto
        {
            Movies = movies,
            Total = preserveTotal ? response.Total : movies.Count,
        };
    }

    public static IReadOnlyList<FolderNodeDto> FilterExcludedFolders(IEnumerable<FolderNodeDto> folders, IEnumerable<string> excludedFolders)
        => folders
            .Where(folder => !IsFolderPathExcluded(folder.Path, excludedFolders))
            .ToList();

    public static bool IsFolderPathExcluded(string path, IEnumerable<string> excludedFolders)
    {
        var normalizedPath = NormalizeFolderPath(path);
        if (string.IsNullOrWhiteSpace(normalizedPath))
        {
            return false;
        }

        foreach (var excluded in excludedFolders)
        {
            var normalizedExcluded = NormalizeFolderPath(excluded);
            if (string.IsNullOrWhiteSpace(normalizedExcluded))
            {
                continue;
            }

            if (string.Equals(normalizedPath, normalizedExcluded, StringComparison.OrdinalIgnoreCase)
                || normalizedPath.StartsWith(normalizedExcluded + "/", StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
        }

        return false;
    }

    public static IEnumerable<MovieDto> SortMovies(IEnumerable<MovieDto> movies, string sort)
    {
        return sort switch
        {
            "name" => movies
                .OrderBy(movie => movie.BestTitle, StringComparer.CurrentCultureIgnoreCase)
                .ThenBy(movie => movie.FolderLevels, StringComparer.CurrentCultureIgnoreCase),
            "release_date_desc" => movies.OrderByDescending(movie => movie.ReleaseDate ?? ""),
            "release_date_asc" => movies.OrderBy(movie => movie.ReleaseDate ?? ""),
            "created_asc" => movies.OrderBy(movie => FirstNonEmpty(movie.CreatedAt, movie.UpdatedAt)),
            "random" => movies.OrderBy(_ => Guid.NewGuid()),
            _ => movies.OrderByDescending(movie => FirstNonEmpty(movie.CreatedAt, movie.UpdatedAt)),
        };
    }

    private static string FirstNonEmpty(params string[] values)
    {
        foreach (var value in values)
        {
            if (!string.IsNullOrWhiteSpace(value))
            {
                return value;
            }
        }

        return "";
    }

    private static string NormalizeFolderPath(string path)
        => (path ?? "").Replace("\\", "/").Trim().Trim('/');
}
