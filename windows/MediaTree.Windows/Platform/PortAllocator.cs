using System.Net;
using System.Net.Sockets;

namespace MediaTree.Windows.Platform;

public static class PortAllocator
{
    public static int GetFreeLoopbackPort()
    {
        using var listener = new TcpListener(IPAddress.Loopback, 0);
        listener.Start();
        return ((IPEndPoint)listener.LocalEndpoint).Port;
    }
}
