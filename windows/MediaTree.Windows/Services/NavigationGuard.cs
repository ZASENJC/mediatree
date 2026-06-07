using System;

namespace MediaTree.Windows.Services;

public static class NavigationGuard
{
    public static bool IsAllowed(string uri, Uri backendUri)
    {
        if (uri.StartsWith("blob:", StringComparison.OrdinalIgnoreCase) ||
            uri.StartsWith("data:", StringComparison.OrdinalIgnoreCase))
        {
            return true;
        }

        if (!Uri.TryCreate(uri, UriKind.Absolute, out var target))
        {
            return false;
        }

        return target.Scheme == backendUri.Scheme &&
               target.Host == backendUri.Host &&
               target.Port == backendUri.Port;
    }
}
