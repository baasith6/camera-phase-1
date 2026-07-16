using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;
using Microsoft.IdentityModel.Tokens;
using Onevo.Api.Domain;

namespace Onevo.Api.Auth;

public class JwtOptions
{
    public string SigningKey { get; set; } = "";
    public string Issuer { get; set; } = "onevo";
    public string Audience { get; set; } = "onevo";
    public int ExpiryHours { get; set; } = 12;
}

public class JwtTokenService
{
    private readonly JwtOptions _opts;
    public JwtTokenService(JwtOptions opts) => _opts = opts;

    public string CreateToken(User user)
    {
        var key = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(_opts.SigningKey));
        var creds = new SigningCredentials(key, SecurityAlgorithms.HmacSha256);

        var claims = new[]
        {
            new Claim(JwtRegisteredClaimNames.Sub, user.Id.ToString()),
            new Claim(JwtRegisteredClaimNames.Email, user.Email),
            new Claim(ClaimTypes.Role, user.Role.ToString()),
            new Claim("uid", user.Id.ToString())
        };

        var token = new JwtSecurityToken(
            issuer: _opts.Issuer,
            audience: _opts.Audience,
            claims: claims,
            expires: DateTime.UtcNow.AddHours(_opts.ExpiryHours),
            signingCredentials: creds);

        return new JwtSecurityTokenHandler().WriteToken(token);
    }
}
