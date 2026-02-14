# 🌐 Connect Cloudflare Domain to Vercel

Follow these steps to link your Cloudflare domain to your Vercel deployment.

---

## 📋 Step-by-Step Guide

### Step 1: Add Domain in Vercel

1. Go to your Vercel dashboard: [vercel.com](https://vercel.com)
2. Click on your project: **fitnessWebApp**
3. Go to **Settings** → **Domains** (or click **Domains** in the top menu)
4. Click **Add Domain**
5. Enter your domain (e.g., `yourdomain.com` or `www.yourdomain.com`)
6. Click **Add**

Vercel will show you the DNS records you need to configure.

---

### Step 2: Configure DNS in Cloudflare

#### Option A: Use CNAME (Recommended for subdomains like www)

1. Go to your Cloudflare dashboard: [dash.cloudflare.com](https://dash.cloudflare.com)
2. Select your domain
3. Go to **DNS** → **Records**
4. Click **Add record**

**For www subdomain:**
- **Type**: `CNAME`
- **Name**: `www`
- **Target**: `cname.vercel-dns.com`
- **Proxy status**: 🟠 **DNS only** (gray cloud - important!)
- Click **Save**

**For root domain (yourdomain.com):**
- **Type**: `A`
- **Name**: `@` (or leave blank)
- **IPv4 address**: `76.76.21.21` (Vercel's IP)
- **Proxy status**: 🟠 **DNS only** (gray cloud)
- Click **Save**

#### Option B: Use Apex Domain (Root domain - yourdomain.com)

Vercel will provide you with specific IP addresses. Use these:

1. In Cloudflare, add **A records**:
   - **Type**: `A`
   - **Name**: `@` (or root domain)
   - **IPv4 address**: `76.76.21.21`
   - **Proxy status**: 🟠 **DNS only** (gray cloud)
   - Click **Save**

2. Add a second A record (if Vercel provides multiple IPs):
   - **Type**: `A`
   - **Name**: `@`
   - **IPv4 address**: `76.76.21.22` (or the second IP Vercel provides)
   - **Proxy status**: 🟠 **DNS only**
   - Click **Save**

---

### Step 3: Important Cloudflare Settings

#### ⚠️ Critical: Disable Proxy (Orange Cloud)

**Very Important**: Make sure the proxy status is **🟠 Gray (DNS only)**, NOT **🟠 Orange (Proxied)**.

- **Gray cloud** = DNS only** ✅ (Correct for Vercel)
- **Orange cloud** = Proxied ❌ (Can cause issues with Vercel)

To change:
1. Find your DNS record in Cloudflare
2. Click the orange cloud icon to turn it gray
3. Click **Save**

#### SSL/TLS Settings

1. Go to **SSL/TLS** in Cloudflare dashboard
2. Set encryption mode to **Full** or **Full (strict)**
3. This ensures HTTPS works correctly

---

### Step 4: Wait for DNS Propagation

1. DNS changes can take **5-60 minutes** to propagate
2. Vercel will automatically detect when DNS is configured correctly
3. You'll see a green checkmark ✅ in Vercel when it's ready

---

### Step 5: Verify in Vercel

1. Go back to Vercel → Your Project → **Domains**
2. You should see your domain listed
3. Status should show **Valid Configuration** ✅
4. If it shows an error, check:
   - DNS records are correct
   - Proxy is disabled (gray cloud)
   - You've waited for propagation

---

## 🎯 Quick Reference

### DNS Records to Add in Cloudflare

**For www.yourdomain.com:**
```
Type: CNAME
Name: www
Target: cname.vercel-dns.com
Proxy: OFF (gray cloud)
```

**For yourdomain.com (root):**
```
Type: A
Name: @
IPv4: 76.76.21.21
Proxy: OFF (gray cloud)
```

---

## 🐛 Troubleshooting

### "Domain not verified" in Vercel
- **Solution**: Wait 5-60 minutes for DNS propagation
- Check that DNS records are correct
- Make sure proxy is disabled (gray cloud)

### "SSL Certificate error"
- **Solution**: Set Cloudflare SSL/TLS to **Full** or **Full (strict)**
- Wait for Vercel to issue SSL certificate (automatic)

### "Domain points to wrong IP"
- **Solution**: Double-check DNS records match Vercel's requirements
- Clear your browser cache
- Use `nslookup yourdomain.com` to verify DNS

### "Site not loading"
- **Solution**: 
  1. Verify DNS records in Cloudflare
  2. Check Vercel deployment is successful
  3. Wait for DNS propagation
  4. Try accessing via `https://yourdomain.com` (not http)

---

## ✅ After Setup

Once configured:
- Your site will be accessible at `https://yourdomain.com`
- Vercel automatically provides SSL certificates
- Both `yourdomain.com` and `www.yourdomain.com` will work (if configured)
- Every deployment automatically updates your custom domain

---

**Need help?** Check Vercel's domain status page for specific error messages and solutions!

