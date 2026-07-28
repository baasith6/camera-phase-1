using MailKit.Net.Smtp;
using MailKit.Security;
using MimeKit;
using Onevo.Api.Domain;

namespace Onevo.Api.Services;

public class SmtpOptions
{
    public bool Enabled { get; set; }
    public string Host { get; set; } = "smtp.gmail.com";
    public int Port { get; set; } = 587;
    public string User { get; set; } = "";
    public string Password { get; set; } = "";
    public string From { get; set; } = "";
    public string? DashboardBaseUrl { get; set; }
}

public class EmailService
{
    private readonly SmtpOptions _opts;
    private readonly ILogger<EmailService> _log;

    public EmailService(SmtpOptions opts, ILogger<EmailService> log)
    {
        _opts = opts;
        _log = log;
    }

    public async Task SendAlertNotificationAsync(
        Store store,
        Camera camera,
        Alert alert,
        CancellationToken ct = default)
    {
        if (!_opts.Enabled)
        {
            _log.LogDebug("SMTP disabled — skipping alert email for {AlertId}", alert.Id);
            return;
        }

        var to = store.NotificationEmail?.Trim();
        if (string.IsNullOrEmpty(to))
        {
            _log.LogWarning("Store {StoreId} has no notification email — skipping alert email", store.Id);
            return;
        }

        var evidence = ParseEvidence(alert.EvidenceJson);
        var alertLink = BuildAlertLink(alert.Id);
        var subject = $"ONEVO alert — {alert.RiskLevel} risk ({alert.RiskScore}) at {store.Name}";

        var bodyText = $"""
            ONEVO risk indicator for staff review (not a theft confirmation).

            Store: {store.Name}
            Camera: {camera.Name}
            Type: {alert.AlertType}
            Risk level: {alert.RiskLevel}
            Score: {alert.RiskScore}

            Evidence:
            {evidence}

            Review in dashboard: {alertLink}
            """;

        var bodyHtml = $"""
            <p><strong>ONEVO risk indicator</strong> for staff review — not a theft confirmation.</p>
            <ul>
              <li><strong>Store:</strong> {Html(store.Name)}</li>
              <li><strong>Camera:</strong> {Html(camera.Name)}</li>
              <li><strong>Type:</strong> {Html(alert.AlertType)}</li>
              <li><strong>Risk level:</strong> {Html(alert.RiskLevel.ToString())}</li>
              <li><strong>Score:</strong> {alert.RiskScore}</li>
            </ul>
            <p><strong>Evidence:</strong></p>
            <ul>{string.Join("", evidence.Split('\n', StringSplitOptions.RemoveEmptyEntries).Select(e => $"<li>{Html(e.Trim())}</li>"))}</ul>
            <p><a href="{Html(alertLink)}">Open alert in dashboard</a></p>
            """;

        var message = new MimeMessage();
        message.From.Add(MailboxAddress.Parse(_opts.From));
        message.To.Add(MailboxAddress.Parse(to));
        message.Subject = subject;
        message.Body = new BodyBuilder { TextBody = bodyText, HtmlBody = bodyHtml }.ToMessageBody();

        try
        {
            using var client = new SmtpClient();
            await client.ConnectAsync(_opts.Host, _opts.Port, SecureSocketOptions.StartTls, ct);
            if (!string.IsNullOrEmpty(_opts.User))
                await client.AuthenticateAsync(_opts.User, _opts.Password, ct);
            await client.SendAsync(message, ct);
            await client.DisconnectAsync(true, ct);
            _log.LogInformation("Alert email sent to {Email} for alert {AlertId}", to, alert.Id);
        }
        catch (Exception ex)
        {
            _log.LogError(ex, "Failed to send alert email to {Email} for alert {AlertId}", to, alert.Id);
        }
    }

    private string BuildAlertLink(Guid alertId)
    {
        var baseUrl = (_opts.DashboardBaseUrl ?? "http://localhost:4200").TrimEnd('/');
        return $"{baseUrl}/alerts/{alertId}";
    }

    private static string ParseEvidence(string evidenceJson)
    {
        try
        {
            var items = System.Text.Json.JsonSerializer.Deserialize<List<string>>(evidenceJson);
            if (items is { Count: > 0 })
                return string.Join("\n", items.Select(e => $"- {e}"));
        }
        catch { /* ignore */ }
        return evidenceJson;
    }

    private static string Html(string value)
        => System.Net.WebUtility.HtmlEncode(value);
}
