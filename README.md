# NovaAiBot - Telegram AI Assistant for Sri Lankan A/L Students

An intelligent Telegram bot specifically designed for Sri Lankan Advanced Level (A/L) Science students. Uses GPT-5 with automatic fallback to Claude and Gemini, supports LaTeX math formatting, and provides expert tutoring in Physics, Chemistry, and Biology.

## Features

- **🤖 Multi-AI Support**: GPT-5 (primary) with automatic fallback to Claude and Gemini
- **📸 Image Analysis**: Send photos of problems, diagrams, equations - AI analyzes and solves them
- **📐 LaTeX Math Formatting**: Proper rendering of mathematical equations and chemical formulas
- **📚 A/L Syllabus Focused**: Tailored for Sri Lankan Advanced Level curriculum
- **🔄 Response Continuation**: Handles long, detailed explanations without truncation
- **📝 Essay & Structured Responses**: Recognizes question types and formats answers appropriately
- **⏱️ Rate Limiting**: 1 free question per user per day (text or image)
- **🎯 Intelligent Model Selection**: Automatically chooses the best model based on question complexity
- **💬 Works in Groups & Private Chats**: Full support for both individual and group conversations
- **📊 Usage Tracking**: Automatic tracking of user questions and statistics
- **🖼️ Vision Models**: GPT-5, Claude 3, and Gemini 1.5 all support image understanding

## Prerequisites

- Python 3.8 or higher
- A Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- **At least ONE of the following AI API keys** (all three recommended for best reliability):
  - OpenAI API Key (from [OpenAI Platform](https://platform.openai.com/api-keys)) - **Primary**
  - Anthropic Claude API Key (from [Anthropic Console](https://console.anthropic.com/)) - **Fallback 1**
  - Google Gemini API Key (from [Google AI Studio](https://makersuite.google.com/app/apikey)) - **Fallback 2**

## Installation

### 1. Clone or Download the Repository

```bash
cd "NovaAiTelegram Bot"
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Set Up Environment Variables

Create a `.env` file in the project directory:

```bash
cp .env.example .env
```

Edit the `.env` file and add your credentials:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# AI API Keys (at least one required, all three recommended)
OPENAI_API_KEY=your_openai_api_key_here
CLAUDE_API_KEY=your_claude_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
```

## Getting Your API Keys

### Telegram Bot Token (Required)

1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` command
3. Follow the instructions to create your bot
4. Copy the bot token provided by BotFather
5. Paste it in your `.env` file as `TELEGRAM_BOT_TOKEN`

### OpenAI API Key (Primary AI - Recommended)

1. Go to [OpenAI Platform](https://platform.openai.com/api-keys)
2. Sign in or create an account
3. Click "Create new secret key"
4. Copy the API key
5. Paste it in your `.env` file as `OPENAI_API_KEY`

**Note:** Uses GPT-5 models via Responses API. Check [OpenAI pricing](https://openai.com/pricing) for details.

### Anthropic Claude API Key (Fallback 1 - Optional but Recommended)

1. Go to [Anthropic Console](https://console.anthropic.com/)
2. Sign up or log in
3. Navigate to API Keys section
4. Create a new API key
5. Paste it in your `.env` file as `CLAUDE_API_KEY`

**Note:** Used as fallback if OpenAI fails. Check [Anthropic pricing](https://www.anthropic.com/pricing) for details.

### Google Gemini API Key (Fallback 2 - Optional)

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the API key
5. Paste it in your `.env` file as `GEMINI_API_KEY`

**Note:** Used as last resort fallback. Gemini API has a generous free tier. Check [Google AI pricing](https://ai.google.dev/pricing) for details.

## How the Fallback System Works

The bot uses a **three-tier fallback system** for maximum reliability:

1. **Primary (GPT-5)**: Tries OpenAI's GPT-5 models first
   - `gpt-5`: For complex questions (>200 chars)
   - `gpt-5-mini`: For standard questions (50-200 chars)
   - `gpt-5-nano`: For simple questions (<50 chars)

2. **Fallback 1 (Claude)**: If OpenAI fails, tries Anthropic Claude
   - Uses Claude 3 Sonnet model
   - Excellent at academic explanations

3. **Fallback 2 (Gemini)**: If both fail, tries Google Gemini
   - Uses Gemini 1.5 Flash model
   - Fast and reliable last resort

**Recommendation**: Configure all three API keys for 99.9% uptime!

## Running the Bot

```bash
python nova_ai_bot.py
```

Or make it executable and run:

```bash
chmod +x nova_ai_bot.py
./nova_ai_bot.py
```

## Bot Commands

**Regular Commands (All Users):**
- `/start` - Start the bot and see welcome message
- `/help` - Display help information
- `/status` - Check remaining daily questions

**Owner Commands (Admin Only):**
- `/settings` - Access bot settings and statistics (Owner only)
- `/broadcast <target> <message>` - Send text announcements to users/groups (Owner only)
- `#broadcast <target> <message>` - Send image with caption to users/groups (photo caption, Owner only)

## Owner/Admin Features

### Setting Up Owner Access

To access admin features, you need to configure your Telegram user ID as the bot owner:

1. **Get Your User ID:**
   - Start the bot and send `/start`
   - Check the console logs, it will display: `[BOT] /start from user YOUR_USER_ID`
   - Alternatively, use [@userinfobot](https://t.me/userinfobot) on Telegram

2. **Configure `.env` File:**
   ```env
   OWNER_USER_ID=123456789  # Replace with your actual user ID
   ```

3. **Restart the Bot:**
   ```bash
   # Stop the bot (Ctrl+C) and restart
   python nova_ai_bot.py
   ```

### Settings Dashboard

Use `/settings` to access the admin dashboard with:

**📊 View Statistics:**
- Total users who have interacted with the bot
- Total questions asked
- Number of active user chats
- Number of active group chats

**📢 Broadcast Messages:**
- Broadcast to all users
- Broadcast to all groups
- Broadcast to everyone (users + groups)

### Broadcasting Messages

Send announcements to all your bot users and groups:

**Syntax:**
```
/broadcast <target> <message>
```

**Targets:**
- `users` - Send to all individual users
- `groups` - Send to all groups where the bot is active
- `all` - Send to both users and groups

**Text Broadcast Examples:**
```
/broadcast users Hello! We've added new features to NovaAI Bot!

/broadcast groups Important: The bot will undergo maintenance tonight at 10 PM.

/broadcast all 🎉 Celebrating 1000 users! Thank you for using NovaAI!
```

### Broadcasting Images with Descriptions

Send announcements with images to make your broadcasts more engaging:

**Syntax:**
1. Select or take a photo
2. Add caption: `#broadcast <target> <message>`
3. Send the photo

**Targets:**
- `#broadcast users <message>` - Send to all users
- `#broadcast groups <message>` - Send to all groups
- `#broadcast all <message>` - Send to everyone

**Image Broadcast Examples:**

**Example 1: New Feature Announcement**
```
1. Take a screenshot of the new feature
2. Add caption: #broadcast all Check out our new AI image analysis feature! 🎉
3. Send the photo
```

**Example 2: Maintenance Notice**
```
1. Create/select an announcement graphic
2. Add caption: #broadcast users The bot will be offline for 30 minutes tonight for upgrades
3. Send the photo
```

**Example 3: Event Promotion**
```
1. Select event poster/image
2. Add caption: #broadcast groups Join our webinar tomorrow at 7 PM! Register now.
3. Send the photo
```

**Features:**
- Automatic tracking of all users and groups
- Success/failure statistics after broadcast
- Rate limiting protection (50ms delay between messages)
- Detailed logging of broadcast results
- Support for both text and image broadcasts
- Images sent with full quality using Telegram's photo API

**Broadcast Report:**
After each broadcast, you'll receive:
- Number of messages successfully sent
- Number of failed deliveries
- Total target count

### Security

- Only the configured OWNER_USER_ID can access admin commands
- Unauthorized attempts are logged and rejected
- All admin actions are logged in the console

## Usage Examples

### Simple Question
```
User: What is Newton's second law?
Bot: Newton's second law states that the acceleration of an object is directly
proportional to the net force acting on it and inversely proportional to its mass.

Mathematically: \(F = ma\)

Where:
- \(F\) = Net force (N)
- \(m\) = Mass (kg)
- \(a\) = Acceleration (m s⁻¹)
```

### Physics Problem
```
User: A 2kg object accelerates at 5 m/s². What force is applied?

Bot: Let's solve this step by step:

**Given:**
- Mass \(m = 2\,\text{kg}\)
- Acceleration \(a = 5\,\text{m s}^{-1}\)

**Formula:**
\[F = ma\]

**Solution:**
\[F = 2 \times 5 = 10\,\text{N}\]

**Answer:** The applied force is 10 N

This follows Newton's second law of motion, which is part of the A/L Physics
syllabus (Unit 2: Mechanics).
```

### Chemistry Question
```
User: What is the standard enthalpy of formation of water?

Bot: The standard enthalpy of formation of water in liquid state is:

\[\Delta H_f^\circ(H_2O(l)) = -285.8\,\text{kJ mol}^{-1}\]

This represents the energy released when 1 mole of liquid water is formed from
its elements in their standard states:

\[H_2(g) + \frac{1}{2}O_2(g) \rightarrow H_2O(l)\]

The negative value indicates it's an exothermic reaction.
```

### Essay-Type Question
```
User: Write an essay on photosynthesis

Bot: # Photosynthesis: The Foundation of Life

## Introduction
Photosynthesis is the fundamental process by which green plants convert light
energy into chemical energy...

## The Process
### Light-Dependent Reactions
The light-dependent reactions occur in the thylakoid membranes...

### Calvin Cycle (Light-Independent Reactions)
The Calvin cycle takes place in the stroma...

## Conclusion
Photosynthesis is essential for life on Earth, providing oxygen and serving as
the primary source of energy for most ecosystems...
```

### Image Analysis - Physics Problem
```
User: [Sends photo of a pulley system] Caption: "Find the tension in the rope"

Bot: Looking at this pulley system, I can see a fixed pulley with a 10kg mass
on one side.

**Given Information (from diagram):**
- Mass m = 10 kg
- System appears to be in equilibrium
- Standard pulley configuration

**Solution:**

For a pulley system in equilibrium, the tension must balance the weight:

\[T = mg\]

Where:
- T = Tension in rope
- m = 10 kg
- g = 9.8 m/s²

**Calculation:**
\[T = 10 × 9.8 = 98 \text{ N}\]

**Answer:** The tension in the rope is 98 N

This problem tests your understanding of forces and equilibrium (A/L Physics
syllabus Unit 2: Mechanics).
```

### Image Analysis - Chemistry Structure
```
User: [Sends photo of molecular structure] Caption: "What is this compound?"

Bot: Analyzing the molecular structure in your image:

**Structure Identification:**
The structure shows:
- A benzene ring (6-carbon aromatic ring)
- An -OH group attached directly to the ring
- Molecular formula: C₆H₅OH

**Compound:** This is **Phenol** (C₆H₅OH)

**Properties:**
- Weak acid due to -OH group
- The benzene ring makes it less acidic than aliphatic alcohols
- Important in organic chemistry synthesis

**Reactions:**
Phenol undergoes:
1. Electrophilic substitution (ortho/para directing)
2. Reaction with NaOH to form sodium phenoxide
3. Reaction with FeCl₃ (violet color test)

This is covered in A/L Chemistry organic chemistry section.
```

### Image Analysis - Biology Diagram
```
User: [Sends photo of cell diagram] Caption: "Label this and explain"

Bot: **Cell Structure Diagram Analysis:**

From your diagram, I can identify:

**Main Components:**
1. **Cell membrane** (outer boundary) - Controls what enters/exits
2. **Nucleus** (large central structure) - Contains genetic material (DNA)
3. **Mitochondria** (oval shapes) - Powerhouse of the cell, produces ATP
4. **Ribosomes** (small dots) - Protein synthesis
5. **Endoplasmic Reticulum** - Protein and lipid transport
6. **Golgi apparatus** - Modifies and packages proteins

**Cell Type:** This appears to be an **animal cell** (eukaryotic)

**Key Features:**
- No cell wall (unlike plant cells)
- No chloroplasts
- Smaller vacuoles

**Functions:**
Each organelle works together:
- Nucleus: Genetic control center
- Mitochondria: Energy production through cellular respiration
  \[\text{C}_6\text{H}_{12}\text{O}_6 + 6\text{O}_2 → 6\text{CO}_2 + 6\text{H}_2\text{O} + \text{ATP}\]

This is fundamental to A/L Biology Unit 1: Cell Biology.
```

## How It Works

### Text Questions
1. **Question Submission**: User types and sends question
2. **Model Selection**: Bot analyzes question complexity and selects appropriate model
3. **AI Processing**: Sends to GPT-5/Claude/Gemini with A/L student system prompt
4. **Response Generation**: AI generates detailed response with proper formatting
5. **LaTeX Conversion**: Math/chemistry formulas converted to Telegram-compatible format
6. **Response Delivery**: Bot sends formatted answer (splits long responses automatically)
7. **Usage Tracking**: Records question in `user_usage.json` (resets daily at midnight)

### Image Questions
1. **Image Upload**: User sends photo (with optional caption)
2. **Image Processing**: Bot downloads and converts to base64 (max 5MB)
3. **Validation**: Checks image size and format
4. **Model Selection**: Always uses most capable vision model (GPT-5 or equivalent)
5. **AI Analysis**: Sends image + text to vision-enabled AI with extended timeout (5 min)
6. **Response Generation**: AI analyzes image and provides detailed explanation
7. **LaTeX Conversion**: Math notation extracted from image converted to proper format
8. **Response Delivery**: Bot sends formatted answer with image analysis
9. **Usage Tracking**: Records as user's daily question

### Fallback Chain
If primary AI (OpenAI) fails:
1. **Try Claude**: Anthropic Claude 3 with vision support
2. **Try Gemini**: Google Gemini 1.5 Flash with vision support
3. **Error**: Only fails if all three services are down

## Image Support 📸

The bot can analyze and explain images of:

### What You Can Send

**Physics:**
- Diagrams of forces, pulleys, circuits
- Graphs (velocity-time, acceleration-time)
- Free body diagrams
- Ray diagrams (optics)
- Wave patterns

**Chemistry:**
- Molecular structures
- Chemical equations
- Apparatus setups
- Reaction mechanisms
- Periodic table sections

**Biology:**
- Cell diagrams
- Organ systems
- Taxonomic charts
- Microscope images
- Ecological diagrams

**Mathematics:**
- Equations from textbooks
- Graphs and plots
- Geometric figures
- Statistical data

### How to Use Images

**With Caption (Recommended):**
```
1. Take/select clear photo
2. Add caption: "Solve this" or "Explain this diagram"
3. Send to bot
```

**Without Caption:**
```
1. Send photo only
2. Bot automatically analyzes and explains
```

### Image Requirements

- **Format**: JPG, PNG (automatically handled by Telegram)
- **Size**: Maximum 5MB
- **Quality**: Clear, readable, well-lit
- **Content**: One problem/diagram per image for best results

### Tips for Best Results

✅ **Good Practices:**
- Take photos in good lighting
- Ensure text/diagrams are clear
- Crop to focus on relevant content
- Add caption for specific questions
- Use high-resolution images

❌ **Avoid:**
- Blurry or dark photos
- Multiple unrelated problems in one image
- Very small text
- Heavily compressed images
- Screenshots with lots of UI elements

## LaTeX Math Support

The bot automatically renders mathematical equations and chemical formulas using Telegram's MarkdownV2 format:

### Examples:

**Inline Math:**
- Input: `$E = mc^2$` → Output: \(E = mc^2\)
- Input: `$\frac{1}{2}mv^2$` → Output: \(\frac{1}{2}mv^2\)

**Display Math:**
- Input: `$$\Delta H_f^\circ = -285.8\,\mathrm{kJ\,mol^{-1}}$$`
- Output: \[\Delta H_f^\circ = -285.8\,\mathrm{kJ\,mol^{-1}}\]

**Chemistry:**
- Input: `$H_2O(l)$` → Output: \(H_2O(l)\)
- Input: `$CO_2(g)$` → Output: \(CO_2(g)\)

The bot handles all LaTeX formatting automatically - no user configuration needed!

## Rate Limiting

- Each user gets 1 free question per 24 hours
- Limit resets at midnight (based on server time)
- Users who exceed the limit are shown:
  - Nova Learn App download link
  - WhatsApp channel link for updates

## Advanced Configuration

### Customizing AI Behavior

You can modify the following in [nova_ai_bot.py](nova_ai_bot.py):

#### Model Selection Logic (Lines 463-475)
```python
if message_length > 200:
    selected_model = 'gpt-5'  # Complex questions
elif message_length > 50:
    selected_model = 'gpt-5-mini'  # Standard questions
else:
    selected_model = 'gpt-5-nano'  # Simple questions
```

#### Response Timeouts (Lines 467, 469, 471)
- Complex questions: 180 seconds (3 minutes)
- Standard questions: 120 seconds (2 minutes)
- Simple questions: 90 seconds (1.5 minutes)

#### Daily Question Limit (Line 89)
```python
return questions_today < 1  # Change 1 to your desired limit
```

#### System Prompt (Lines 195-238)
Customize the AI teacher's behavior by editing the `get_default_system_prompt()` function.

### A/L Student Features

The bot includes specialized features for Sri Lankan Advanced Level students:

#### Syllabus Compliance
- **Only uses derivations from A/L syllabus**
- Avoids out-of-syllabus methods
- Informs students when topics are beyond syllabus

#### Question Type Recognition
- **Essay Questions**: Provides structured answers with Introduction, Body, Conclusion
- **Structured Questions**: Uses headings, bullet points, and organized formatting
- **Problem-Solving**: Step-by-step solutions with explanations

#### Subject Support
- **Physics**: Mechanics, Electricity, Waves, Modern Physics
- **Chemistry**: Physical, Organic, Inorganic Chemistry
- **Biology**: Botany, Zoology, Human Biology

#### Language Support
The system prompt includes instructions for:
- English (default)
- Tamil (தமிழ்)
- Sinhala (සිංහල)

*Note: Current version responds primarily in English. Full multilingual support coming soon!*

## File Structure

```
NovaAiTelegram Bot/
├── nova_ai_bot.py      # Main bot script with AI integration
├── requirements.txt    # Python dependencies (aiohttp, python-telegram-bot)
├── .env.example       # Environment variables template
├── .env              # Your actual credentials (create this, not in git)
├── .gitignore        # Git ignore rules
├── user_usage.json   # User tracking data (auto-generated)
└── README.md         # This comprehensive guide
```

### Key Components in nova_ai_bot.py

- **Lines 119-188**: LaTeX formatting utilities
- **Lines 195-238**: A/L-focused system prompt
- **Lines 253-340**: OpenAI GPT-5 API with continuation logic
- **Lines 364-409**: Claude API fallback
- **Lines 412-455**: Gemini API fallback
- **Lines 458-514**: Main AI response logic with fallback chain
- **Lines 571-701**: Question handler with rate limiting and formatting

## Deployment

### Running 24/7 on a Server

For production deployment, consider:

1. **Using a VPS** (DigitalOcean, AWS, etc.)
2. **Running with systemd** (Linux):

Create `/etc/systemd/system/novaaibot.service`:

```ini
[Unit]
Description=NovaAI Telegram Bot
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/NovaAiTelegram Bot
Environment="PATH=/usr/bin:/usr/local/bin"
ExecStart=/usr/bin/python3 /path/to/NovaAiTelegram Bot/nova_ai_bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable novaaibot
sudo systemctl start novaaibot
```

3. **Using Docker** (optional - create your own Dockerfile)
4. **Using screen or tmux** for simple background running

## Adding Bot to Groups

1. Add the bot to your Telegram group
2. (Optional) Make it an admin if you want it to see all messages
3. By default, bots in groups only see:
   - Messages that start with `/`
   - Messages that mention the bot
   - Replies to the bot's messages

To make the bot see all messages in a group:
1. Go to @BotFather
2. Send `/mybots`
3. Select your bot
4. Go to "Bot Settings" → "Group Privacy"
5. Turn OFF "Group Privacy"

## Troubleshooting

### Bot doesn't respond
- Check if the bot is running: `python nova_ai_bot.py`
- Verify your `TELEGRAM_BOT_TOKEN` is correct in `.env`
- Check console logs for error messages
- Ensure bot has been started with `/start` command in Telegram
- In groups: make sure bot can see messages (disable Group Privacy in BotFather)

### AI API Errors

#### "All AI services failed to respond"
- **Check API keys**: Ensure at least one API key is configured correctly
- **Check credits**: Verify you have credits/quota on your AI provider accounts
- **Check logs**: Look for specific error messages in console (e.g., "OPENAI_TIMEOUT", "401 Unauthorized")
- **Solution**: Configure multiple API keys for better reliability

#### OpenAI Timeout Errors
- **Normal for complex questions**: GPT-5 can take 1-3 minutes for detailed answers
- **Check network**: Ensure stable internet connection
- **Try again**: Bot automatically retries with faster models
- **Fallback works**: Claude or Gemini should respond if OpenAI times out

#### Authentication Errors (401)
- OpenAI: Regenerate key at https://platform.openai.com/api-keys
- Claude: Check key at https://console.anthropic.com/
- Gemini: Verify key at https://makersuite.google.com/app/apikey
- **Don't share keys**: Never commit `.env` to git or share publicly

#### Rate Limit Errors (429)
- **OpenAI**: You've exceeded your rate limit or quota
- **Solution**: Wait a few minutes or upgrade your plan
- **Fallback**: Bot will try Claude/Gemini automatically

### LaTeX Rendering Issues

#### Math not rendering
- Telegram app may not support all LaTeX
- Try different Telegram client (Desktop vs Mobile)
- Some complex equations may need simplification
- **Fallback**: Bot sends plain text if MarkdownV2 fails

#### Special characters appearing
- This is normal MarkdownV2 escaping (e.g., `\_`, `\*`)
- Telegram renders them correctly in the app
- Don't worry about backslashes in console logs

### Permission/File Errors
- Ensure `user_usage.json` is writable: `chmod 644 user_usage.json`
- Check directory permissions: `ls -la`
- Bot creates `user_usage.json` automatically on first run

### Long Response Issues
- **Response cut off**: Increase timeouts in code (lines 467-471)
- **Multiple messages**: Normal for responses >4000 characters
- **Continuation failed**: Check logs for specific error
- **Solution**: Bot automatically splits long responses

### Installation Issues

#### Module not found
```bash
# Ensure you're in the correct directory
cd "NovaAiTelegram Bot"

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

#### Python version issues
```bash
# Check Python version (needs 3.8+)
python --version

# Use python3 if needed
python3 nova_ai_bot.py
```

### Image-Specific Issues

#### "Image Too Large" Error
- **Problem**: Image exceeds 5MB limit
- **Solutions**:
  - Crop image to focus on relevant content
  - Compress using image editor or online tool
  - Take photo at lower resolution
  - Use JPEG instead of PNG (usually smaller)

#### Image Not Recognized
- **Problem**: Bot doesn't detect the image
- **Solutions**:
  - Send as photo, not as file/document
  - Don't forward from other chats (download and resend)
  - Check image actually uploaded (look for thumbnail)

#### Poor Analysis Quality
- **Problem**: AI misinterprets image content
- **Solutions**:
  - Retake photo in better lighting
  - Ensure image is in focus
  - Crop out distracting elements
  - Add descriptive caption
  - Try different angle

#### "Failed to process image" Error
- **Problem**: Technical issue processing image
- **Solutions**:
  - Wait a moment and try again
  - Convert image format (JPG ↔ PNG)
  - Reduce image size
  - Check internet connection

### Debug Mode

Enable detailed logging by changing line 33:
```python
level=logging.DEBUG  # Change from INFO to DEBUG
```

This will show:
- Full API requests/responses
- LaTeX conversion details
- Fallback chain execution
- Image processing details
- Detailed error traces

## Links

- Nova Learn App: https://play.google.com/store/apps/details?id=com.NovaScience.nova_science&ppcampaignidweb_share
- WhatsApp Channel: https://whatsapp.com/channel/0029Vb6hoKxBKfhyA1UJ4u2K

## License

This project is provided as-is for educational purposes.

## Support

For questions or issues, join our WhatsApp channel: https://whatsapp.com/channel/0029Vb6hoKxBKfhyA1UJ4u2K
