using System.Text.Json.Serialization;

namespace MediaTree.Windows.Models;

public sealed class AuthStatusDto
{
    [JsonPropertyName("need_auth")]
    public bool NeedAuth { get; set; }

    [JsonPropertyName("auth_configured")]
    public bool AuthConfigured { get; set; }
}

public sealed class AuthResponseDto
{
    [JsonPropertyName("token")]
    public string Token { get; set; } = "";

    [JsonPropertyName("ok")]
    public bool Ok { get; set; }
}

public sealed class MediaTokenResponseDto
{
    [JsonPropertyName("token")]
    public string Token { get; set; } = "";

    [JsonPropertyName("expires_at")]
    public long ExpiresAt { get; set; }
}

