# Webhook Deployment Guide

## Overview

This guide explains how to set up and configure Wix webhooks for real-time order processing with the Wix Printer Service.

## Prerequisites

- Wix Printer Service installed and running
- Public URL or domain pointing to your Raspberry Pi
- Wix site with orders API access
- SSL certificate (required for webhooks)

## Step 1: Configure Environment Variables

Add the following webhook configuration to your `.env` file:

```bash
# Wix Webhook Configuration
WIX_WEBHOOK_SECRET=your_webhook_secret_here
WIX_WEBHOOK_REQUIRE_SIGNATURE=true
```

### Generating Webhook Secret

1. Generate a secure random string (32+ characters)
2. Use the same secret in both Wix webhook configuration and your service

```bash
# Example: Generate a secure webhook secret
openssl rand -hex 32
```

## Step 2: Set Up Public URL

### Option A: Cloudflare Tunnel (Recommended)

```bash
# Install Cloudflare Tunnel
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
sudo dpkg -i cloudflared.deb

# Create tunnel
cloudflared tunnel --url http://localhost:8000
```

### Option B: Router Port Forwarding

1. Configure your router to forward port 8000 to your Raspberry Pi
2. Ensure you have a static IP or dynamic DNS
3. Set up SSL certificate (Let's Encrypt recommended)

### Option C: ngrok (Development/Testing)

```bash
# Install ngrok
sudo snap install ngrok

# Create tunnel
ngrok http 8000
```

## Step 3: Configure Wix Webhooks

1. **Log in to Wix Dashboard**
   - Go to your site's dashboard
   - Navigate to Settings → Webhooks

2. **Create New Webhook**
   - Click "Add Webhook"
   - Name: "Order Processing Webhook"
   - URL: `https://your-domain.com/webhook/orders`
   - Events: Select order-related events:
     - `OrderCreated`
     - `OrderUpdated` 
     - `OrderPaid`

3. **Configure Webhook Security**
   - Set webhook secret (same as WIX_WEBHOOK_SECRET)
   - Enable signature verification
   - Set content type to `application/json`

## Step 4: Test Webhook Configuration

### Test Webhook Endpoint

```bash
# Test webhook endpoint is accessible
curl -X POST https://your-domain.com/webhook/orders \
  -H "Content-Type: application/json" \
  -H "X-Wix-Webhook-Signature: test" \
  -d '{"eventType": "test", "data": {}}'
```

### Check Webhook Statistics

```bash
# Monitor webhook processing
curl https://your-domain.com/webhook/statistics
```

### Test Order Processing

1. Create a test order in your Wix site
2. Check service logs: `sudo journalctl -u wix-printer.service -f`
3. Verify print job creation: `curl http://localhost:8000/print/statistics`

## Step 5: Monitor and Maintain

### Health Monitoring

The webhook system includes comprehensive monitoring:

- **Webhook Statistics**: `/webhook/statistics`
- **Health Metrics**: `/health/metrics`
- **Rate Limiting**: 100 requests/minute per endpoint

### Log Monitoring

```bash
# Monitor webhook processing logs
sudo journalctl -u wix-printer.service -f | grep webhook

# Check for webhook errors
sudo journalctl -u wix-printer.service | grep "webhook.*error"
```

### Performance Monitoring

```bash
# Check webhook processing times
curl http://localhost:8000/webhook/statistics | jq '.webhook_statistics'

# Monitor rate limiting
curl http://localhost:8000/webhook/statistics | jq '.rate_limit_status'
```

## Troubleshooting

### Common Issues

#### 1. Webhook Signature Validation Fails

**Symptoms**: 401 errors, "Invalid webhook signature" messages

**Solutions**:
- Verify `WIX_WEBHOOK_SECRET` matches Wix configuration
- Check webhook secret is properly URL-encoded
- Ensure signature header format is correct

#### 2. Rate Limiting Triggered

**Symptoms**: 429 errors, "Rate limit exceeded" messages

**Solutions**:
- Check for webhook retry loops
- Verify Wix isn't sending duplicate webhooks
- Consider increasing rate limits if needed

#### 3. SSL Certificate Issues

**Symptoms**: Webhook delivery failures from Wix

**Solutions**:
- Ensure SSL certificate is valid and not expired
- Use Let's Encrypt for free SSL certificates
- Test SSL configuration with online tools

#### 4. Network Connectivity

**Symptoms**: Webhooks not reaching your service

**Solutions**:
- Verify public URL is accessible from internet
- Check firewall settings on router and Raspberry Pi
- Test with curl from external network

### Debug Commands

```bash
# Test webhook endpoint locally
curl -X POST http://localhost:8000/webhook/orders \
  -H "Content-Type: application/json" \
  -d '{"eventType": "OrderCreated", "data": {"id": "test-order"}}'

# Check webhook health metrics
curl http://localhost:8000/health/metrics | jq '.webhook'

# Reset webhook statistics
curl -X POST http://localhost:8000/webhook/reset-stats
```

## Security Best Practices

1. **Always use HTTPS** for webhook endpoints
2. **Validate webhook signatures** - never disable signature validation in production
3. **Implement rate limiting** to prevent abuse
4. **Monitor webhook logs** for suspicious activity
5. **Use strong webhook secrets** (32+ random characters)
6. **Restrict CORS origins** to Wix domains only
7. **Keep webhook secrets secure** - never commit to version control

## Performance Optimization

1. **Process webhooks asynchronously** when possible
2. **Implement duplicate detection** to handle retries
3. **Monitor processing times** and optimize slow operations
4. **Use connection pooling** for database operations
5. **Implement graceful degradation** during high load

## Backup and Recovery

1. **Backup webhook configuration** including secrets
2. **Document webhook URLs** and settings
3. **Test webhook failover** scenarios
4. **Monitor webhook delivery success rates**
5. **Implement webhook replay** for failed deliveries

## Support and Maintenance

### Regular Maintenance Tasks

- Monitor webhook success rates weekly
- Review webhook logs for errors monthly
- Update SSL certificates before expiration
- Test webhook processing after system updates

### Getting Help

- Check service logs: `sudo journalctl -u wix-printer.service`
- Review webhook statistics: `/webhook/statistics`
- Test individual components with provided debug commands
- Consult Wix webhook documentation for API changes
