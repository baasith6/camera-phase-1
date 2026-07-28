using System.Security.Claims;
using Onevo.Api.Domain;

namespace Onevo.Api.Auth;

/// <summary>Helpers for multi-store tenancy: Admins see all; others scoped to User.StoreId.</summary>
public static class TenantAccess
{
    public static Guid CurrentUserId(ClaimsPrincipal user)
        => Guid.TryParse(user.FindFirstValue("uid"), out var id) ? id : Guid.Empty;

    public static UserRole CurrentRole(ClaimsPrincipal user)
        => Enum.TryParse<UserRole>(user.FindFirstValue(ClaimTypes.Role), true, out var r)
            ? r : UserRole.Reviewer;

    public static Guid? CurrentStoreId(ClaimsPrincipal user)
        => Guid.TryParse(user.FindFirstValue("storeId"), out var id) ? id : null;

    public static bool IsAdmin(ClaimsPrincipal user) => CurrentRole(user) is UserRole.Admin;

    public static bool CanAccessStore(ClaimsPrincipal user, Guid storeId)
    {
        if (IsAdmin(user)) return true;
        var userStore = CurrentStoreId(user);
        return userStore is not null && userStore.Value == storeId;
    }

    public static IQueryable<Store> ScopeStores(IQueryable<Store> query, ClaimsPrincipal user)
    {
        if (IsAdmin(user)) return query;
        var storeId = CurrentStoreId(user);
        return storeId is null ? query.Where(_ => false) : query.Where(s => s.Id == storeId);
    }

    public static IQueryable<Camera> ScopeCameras(IQueryable<Camera> query, ClaimsPrincipal user)
    {
        if (IsAdmin(user)) return query;
        var storeId = CurrentStoreId(user);
        return storeId is null ? query.Where(_ => false) : query.Where(c => c.StoreId == storeId);
    }

    public static IQueryable<Alert> ScopeAlerts(IQueryable<Alert> query, ClaimsPrincipal user)
    {
        if (IsAdmin(user)) return query;
        var storeId = CurrentStoreId(user);
        return storeId is null ? query.Where(_ => false) : query.Where(a => a.StoreId == storeId);
    }

    public static IQueryable<Connector> ScopeConnectors(IQueryable<Connector> query, ClaimsPrincipal user)
    {
        if (IsAdmin(user)) return query;
        var storeId = CurrentStoreId(user);
        return storeId is null ? query.Where(_ => false) : query.Where(c => c.StoreId == storeId);
    }
}
