namespace MediaTree.Windows.Models;

public enum AuthSessionState
{
    Ready,
    CreatedLocalAccount,
    NeedsUserLogin,
}

public sealed record AuthSessionResult(AuthSessionState State, string Message);

