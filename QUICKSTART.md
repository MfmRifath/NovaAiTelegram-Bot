# Quick Start Guide - NovaAiBot

Get your bot running in 5 minutes!

## Step 1: Install Dependencies

```bash
cd "NovaAiTelegram Bot"
pip install -r requirements.txt
```

## Step 2: Get API Keys

### Required: Telegram Bot Token
1. Open Telegram → Search for @BotFather
2. Send `/newbot` and follow instructions
3. Copy the token

### Recommended: OpenAI API Key (Primary)
1. Go to https://platform.openai.com/api-keys
2. Sign up and create a new secret key
3. Copy the key

### Optional: Claude API Key (Fallback 1)
1. Go to https://console.anthropic.com/
2. Sign up and create API key
3. Copy the key

### Optional: Gemini API Key (Fallback 2)
1. Go to https://makersuite.google.com/app/apikey
2. Sign in with Google
3. Create and copy API key

## Step 3: Configure Environment

```bash
cp .env.example .env
nano .env  # or use any text editor
```

Add your keys:
```env
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
OWNER_USER_ID=your_user_id  # Optional - for admin features
OPENAI_API_KEY=sk-proj-abc123...
CLAUDE_API_KEY=sk-ant-abc123...  # Optional
GEMINI_API_KEY=AIzaSy...  # Optional
```

**Important:** You need at least TELEGRAM_BOT_TOKEN and ONE AI key (OpenAI recommended).

**Finding Your User ID (for Admin Features):**
1. Start the bot first (without OWNER_USER_ID)
2. Send `/start` to your bot
3. Check the console logs - it will show your user ID
4. Copy your user ID and add it to `.env` as OWNER_USER_ID
5. Restart the bot

## Step 4: Run the Bot

```bash
python nova_ai_bot.py
```

You should see:
```
INFO:__main__:NovaAiBot is starting...
```

## Step 5: Test in Telegram

1. Open Telegram
2. Search for your bot by username (the one you gave to BotFather)
3. Send `/start`
4. Try these tests:
   - Text question: "What is Newton's first law?"
   - Photo: Take a photo of a physics problem and send it
   - Photo with caption: Send image with caption "Solve this"

## Common Issues

### "TELEGRAM_BOT_TOKEN not found"
- Check your `.env` file exists
- Make sure there are no spaces around the `=` sign
- Verify the token is correct from BotFather

### "All AI services failed"
- Check at least one AI API key is configured
- Verify the API key is valid and has credits
- Check console logs for specific error

### Bot doesn't respond in groups
- Go to @BotFather → select your bot
- Bot Settings → Group Privacy → Turn OFF

### "Image Too Large" error
- Maximum image size: 5MB
- Crop or compress the image
- Use JPEG format (smaller than PNG)

## Next Steps

- Read the full [README.md](README.md) for advanced configuration
- Add bot to your study groups
- Configure all three AI services for maximum reliability
- Customize the system prompt for your specific needs

## Quick Reference

**Start/Stop Bot:**
```bash
python nova_ai_bot.py  # Start
Ctrl+C                  # Stop
```

**View Logs:**
```bash
python nova_ai_bot.py 2>&1 | tee bot.log
```

**Run in Background (Linux/Mac):**
```bash
nohup python nova_ai_bot.py > bot.log 2>&1 &
```

**Stop Background Process:**
```bash
ps aux | grep nova_ai_bot.py
kill <PID>
```

## Support

- Issues? Check [README.md](README.md) Troubleshooting section
- Join WhatsApp: https://whatsapp.com/channel/0029Vb6hoKxBKfhyA1UJ4u2K
- For unlimited access: Download Nova Learn App

Happy Learning! 🎓
