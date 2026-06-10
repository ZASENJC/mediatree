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
        int limit)
    {
        var responseList = responses.ToList();
        var movies = responseList.SelectMany(response => response.Movies);
        return new MoviesResponseDto
        {
            Movies = SortMovies(movies, sort).Take(Math.Max(0, limit)).ToList(),
            Total = responseList.Sum(response => response.Total),
        };
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
}
