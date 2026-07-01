#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════╗
# ║  Looper Linux Installer                                         ║
# ║  Tested on: Linux Mint 22.x, Ubuntu 22.04/24.04, Debian 12,    ║
# ║             Fedora 39/40, Arch Linux                            ║
# ║                                                                 ║
# ║  Run:  bash install.sh                                          ║
# ║  Or:   curl -sSL https://raw.githubusercontent.com/Shango46/   ║
# ║          Looper/main/installer/install.sh | bash                ║
# ╚══════════════════════════════════════════════════════════════════╝

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────────
REPO_URL="https://github.com/Shango46/Looper.git"
INSTALL_DIR="$HOME/.local/share/looper"
BIN_DIR="$HOME/.local/bin"
ICON_DIR="$HOME/.local/share/icons/hicolor/128x128/apps"
APP_DIR="$HOME/.local/share/applications"
DESKTOP_DIR="$HOME/Desktop"
LAUNCHER="$INSTALL_DIR/looper-launch.sh"
ICON_PNG="$ICON_DIR/looper.png"
DESKTOP_FILE="$APP_DIR/looper.desktop"
DESKTOP_SHORTCUT="$DESKTOP_DIR/Looper.desktop"
PORT=8731

# ── Colours ────────────────────────────────────────────────────────────────────
GRN='\033[0;32m'; YLW='\033[1;33m'; RED='\033[0;31m'; BLU='\033[1;34m'; NC='\033[0m'
log()  { echo -e "${GRN}[Looper]${NC} $*"; }
warn() { echo -e "${YLW}[Looper]${NC} WARNING: $*"; }
err()  { echo -e "${RED}[Looper]${NC} ERROR: $*" >&2; exit 1; }
step() { echo -e "\n${BLU}━━  $*${NC}"; }

# ── Banner ─────────────────────────────────────────────────────────────────────
echo -e "${BLU}"
echo "  ██╗      ██████╗  ██████╗ ██████╗ ███████╗██████╗ "
echo "  ██║     ██╔═══██╗██╔═══██╗██╔══██╗██╔════╝██╔══██╗"
echo "  ██║     ██║   ██║██║   ██║██████╔╝█████╗  ██████╔╝"
echo "  ██║     ██║   ██║██║   ██║██╔═══╝ ██╔══╝  ██╔══██╗"
echo "  ███████╗╚██████╔╝╚██████╔╝██║     ███████╗██║  ██║"
echo "  ╚══════╝ ╚═════╝  ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═╝"
echo -e "${NC}"
echo "  AI Company Platform — Linux Installer"
echo "  Installing to: $INSTALL_DIR"
echo ""

# ── Detect package manager ─────────────────────────────────────────────────────
step "Detecting system"

PKG_MANAGER=""
if command -v apt-get &>/dev/null; then
    PKG_MANAGER="apt"
    log "Package manager: apt (Debian/Ubuntu/Mint)"
elif command -v dnf &>/dev/null; then
    PKG_MANAGER="dnf"
    log "Package manager: dnf (Fedora/RHEL)"
elif command -v pacman &>/dev/null; then
    PKG_MANAGER="pacman"
    log "Package manager: pacman (Arch)"
else
    warn "No recognised package manager found. Auto-install of missing dependencies will be skipped."
fi

# Check sudo availability (prompt once upfront so we don't interrupt later)
HAS_SUDO=false
if command -v sudo &>/dev/null; then
    log "Checking sudo access (you may be prompted for your password)..."
    if sudo -v 2>/dev/null; then
        HAS_SUDO=true
        # Keep sudo timestamp alive in background
        ( while true; do sudo -n true; sleep 50; done ) &
        SUDO_KEEPALIVE_PID=$!
        trap 'kill "$SUDO_KEEPALIVE_PID" 2>/dev/null' EXIT
    else
        warn "sudo not available or password incorrect. Will skip system package installs."
    fi
fi

pkg_install() {
    # Usage: pkg_install <apt-pkg> [dnf-pkg] [pacman-pkg]
    local apt_pkg="${1:-}" dnf_pkg="${2:-$1}" pac_pkg="${3:-$1}"
    if [ "$HAS_SUDO" = false ]; then
        warn "Skipping install of '$apt_pkg' (no sudo). Please install it manually."
        return 1
    fi
    case "$PKG_MANAGER" in
        apt)    sudo apt-get install -y "$apt_pkg" ;;
        dnf)    sudo dnf install -y "$dnf_pkg" ;;
        pacman) sudo pacman -S --noconfirm "$pac_pkg" ;;
        *)      warn "Cannot auto-install '$apt_pkg' — install it manually."; return 1 ;;
    esac
}

# ── Git ────────────────────────────────────────────────────────────────────────
step "Checking Git"

if ! command -v git &>/dev/null; then
    log "Installing Git..."
    if ! pkg_install git; then
        err "Git is required but could not be installed. Install it manually and re-run."
    fi
fi
log "Git: $(git --version)"

# ── Clone or update repo ───────────────────────────────────────────────────────
step "Fetching Looper source"

mkdir -p "$(dirname "$INSTALL_DIR")"

if [ -d "$INSTALL_DIR/.git" ]; then
    log "Looper already cloned — pulling latest changes..."
    git -C "$INSTALL_DIR" pull --ff-only || warn "git pull failed; continuing with existing files."
else
    if [ -d "$INSTALL_DIR" ]; then
        warn "$INSTALL_DIR exists but is not a git repo. Moving it to ${INSTALL_DIR}.bak"
        mv "$INSTALL_DIR" "${INSTALL_DIR}.bak"
    fi
    log "Cloning Looper from GitHub..."
    git clone --depth=1 "$REPO_URL" "$INSTALL_DIR"
fi
log "Source at: $INSTALL_DIR"

# ── Python 3.11 ───────────────────────────────────────────────────────────────
step "Checking Python 3.11"

PYTHON311=""

# Try the Python launcher (py -3.11)
if command -v py &>/dev/null && py -3.11 --version &>/dev/null 2>&1; then
    PYTHON311="$(py -3.11 -c 'import sys; print(sys.executable)')"

# Try python3.11 directly
elif command -v python3.11 &>/dev/null; then
    PYTHON311="$(command -v python3.11)"

# Try python3 if it's 3.11
elif command -v python3 &>/dev/null; then
    _ver="$(python3 -c 'import sys; print(sys.version_info[:2])')"
    if [ "$_ver" = "(3, 11)" ]; then
        PYTHON311="$(command -v python3)"
    fi
fi

if [ -z "$PYTHON311" ]; then
    log "Python 3.11 not found — installing..."
    case "$PKG_MANAGER" in
        apt)
            sudo apt-get update -qq
            # Try standard repos first. Ubuntu 24.04 / Mint 22.x include python3.11
            # but may not have python3.11-venv in the default package list.
            if ! sudo apt-get install -y python3.11 python3.11-venv python3.11-dev 2>/dev/null; then
                log "python3.11 not in standard repos. Adding deadsnakes PPA..."
                sudo apt-get install -y software-properties-common
                sudo add-apt-repository -y ppa:deadsnakes/ppa
                sudo apt-get update -qq
                sudo apt-get install -y python3.11 python3.11-venv python3.11-dev
            fi
            PYTHON311="$(command -v python3.11)"
            ;;
        dnf)
            sudo dnf install -y python3.11 python3.11-devel
            PYTHON311="$(command -v python3.11)"
            ;;
        pacman)
            # Arch rolling release — python is typically 3.11+ in AUR or extra
            sudo pacman -S --noconfirm python 2>/dev/null || true
            PYTHON311="$(command -v python3 2>/dev/null || command -v python)"
            ;;
        *)
            err "Cannot auto-install Python 3.11. Please install it manually and re-run."
            ;;
    esac
fi

if [ -z "$PYTHON311" ] || ! "$PYTHON311" --version &>/dev/null 2>&1; then
    err "Python 3.11 could not be located after install attempt."
fi
log "Python: $PYTHON311 ($(\"$PYTHON311\" --version))"

# ── Virtual environment ────────────────────────────────────────────────────────
step "Creating Python virtual environment"

VENV_DIR="$INSTALL_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

if [ -d "$VENV_DIR" ]; then
    log "Existing venv found — removing for clean install..."
    rm -rf "$VENV_DIR"
fi

"$PYTHON311" -m venv "$VENV_DIR"
log "Venv created at: $VENV_DIR"

# ── Python dependencies ───────────────────────────────────────────────────────
step "Installing Python dependencies (this may take a few minutes)"

"$VENV_PYTHON" -m pip install --upgrade pip --quiet
"$VENV_PIP" install -r "$INSTALL_DIR/requirements.txt"
log "Python packages installed."

# ── Node.js ───────────────────────────────────────────────────────────────────
step "Checking Node.js"

NODE_OK=false
if command -v node &>/dev/null && node --version &>/dev/null 2>&1; then
    _node_major="$(node --version | sed 's/v\([0-9]*\).*/\1/')"
    if [ "${_node_major:-0}" -ge 18 ]; then
        NODE_OK=true
        log "Node.js: $(node --version)"
    else
        warn "Node.js $(node --version) is too old (need ≥18). Attempting upgrade..."
    fi
fi

if [ "$NODE_OK" = false ]; then
    log "Installing Node.js 20 LTS..."
    case "$PKG_MANAGER" in
        apt)
            if "$HAS_SUDO" && command -v curl &>/dev/null; then
                curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - 2>/dev/null
                sudo apt-get install -y nodejs
                NODE_OK=true
            fi
            ;;
        dnf)
            if "$HAS_SUDO"; then
                sudo dnf install -y nodejs npm
                NODE_OK=true
            fi
            ;;
        pacman)
            if "$HAS_SUDO"; then
                sudo pacman -S --noconfirm nodejs npm
                NODE_OK=true
            fi
            ;;
    esac

    # Fallback: install via nvm (no sudo required)
    if [ "$NODE_OK" = false ] && command -v curl &>/dev/null; then
        log "Trying nvm (no-root Node.js install)..."
        export NVM_DIR="$HOME/.nvm"
        if [ ! -d "$NVM_DIR" ]; then
            curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
        fi
        # shellcheck source=/dev/null
        [ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"
        nvm install 20 && nvm use 20 && NODE_OK=true || true
    fi

    if [ "$NODE_OK" = false ]; then
        warn "Could not install Node.js. n8n automation features will be unavailable."
        warn "Install Node.js 20 LTS manually from https://nodejs.org and re-run this installer."
    else
        log "Node.js: $(node --version)"
    fi
fi

# ── n8n ───────────────────────────────────────────────────────────────────────
step "Installing n8n"

if [ "$NODE_OK" = true ] && command -v npm &>/dev/null; then
    # Configure npm to install to ~/.local so no sudo is needed on systems where
    # npm was installed via apt (which defaults to /usr/lib/node_modules, root-only).
    npm config set prefix "$HOME/.local" 2>/dev/null || true

    # Add ~/.local/bin to PATH now in case it wasn't there already
    export PATH="$HOME/.local/bin:$PATH"

    log "Installing n8n globally to ~/.local (this may take a few minutes)..."
    # --legacy-peer-deps: n8n 2.x has peer dependency conflicts in its dependency
    # tree (zod version mismatches); these are internal to n8n and safe to override.
    npm install -g n8n --legacy-peer-deps --quiet 2>/dev/null \
        && log "n8n installed." \
        || warn "n8n install had warnings — automations may still work."
else
    warn "Skipping n8n install (Node.js not available)."
fi

# ── Playwright Chromium ───────────────────────────────────────────────────────
step "Installing browser automation engine (Playwright Chromium ~150 MB)"

"$VENV_PYTHON" -m playwright install chromium \
    && log "Playwright Chromium installed." \
    || warn "Playwright install failed. Browser automation won't work until you run it manually."

# ── Icon ──────────────────────────────────────────────────────────────────────
step "Generating application icon"

mkdir -p "$ICON_DIR"

"$VENV_PIP" install pillow --quiet 2>/dev/null || true

"$VENV_PYTHON" - "$ICON_PNG" <<'PYEOF'
import math, os, sys
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Pillow not available — skipping icon generation")
    sys.exit(0)

def _font(size):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default()

def make(out, size=128):
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad  = max(1, size // 14)
    r    = size // 4
    draw.rounded_rectangle([pad, pad, size-1-pad, size-1-pad],
                           radius=r, fill=(76, 29, 149, 255))
    pad2 = pad + max(1, size // 22)
    draw.rounded_rectangle([pad2, pad2, size-1-pad2, size-1-pad2],
                           radius=max(2, r-3), fill=(109, 40, 217, 255))
    cx, cy = size / 2, size / 2
    arc_r  = size * 0.30
    arc_w  = max(2, size // 9)
    bbox   = [cx-arc_r, cy-arc_r, cx+arc_r, cy+arc_r]
    draw.arc(bbox, start=120, end=60, fill=(255,255,255,255), width=arc_w)
    tip = math.radians(60)
    tx, ty = cx + arc_r * math.cos(tip), cy + arc_r * math.sin(tip)
    tang = tip + math.pi / 2
    al   = max(3, size // 7)
    sp   = math.pi * 0.38
    draw.polygon([(tx, ty),
                  (tx + al*math.cos(tang-sp), ty + al*math.sin(tang-sp)),
                  (tx + al*math.cos(tang+sp), ty + al*math.sin(tang+sp))],
                 fill=(255,255,255,255))
    fs   = max(6, int(size * 0.22))
    font = _font(fs)
    bt   = draw.textbbox((0, 0), "L", font=font)
    tw, th = bt[2]-bt[0], bt[3]-bt[1]
    draw.text((cx - tw/2 - bt[0], cy - th/2 - bt[1]), "L",
              fill=(255,255,255,200), font=font)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    img.save(out, "PNG")
    print(f"Icon written: {out}")

make(sys.argv[1] if len(sys.argv) > 1 else "looper.png")
PYEOF

if [ -f "$ICON_PNG" ]; then
    log "Icon: $ICON_PNG"
else
    warn "Icon generation failed — shortcuts will use a generic icon."
    ICON_PNG="application-x-executable"   # fall back to system icon name
fi

# ── Launcher script ────────────────────────────────────────────────────────────
step "Creating launcher"

cat > "$LAUNCHER" <<LAUNCHER
#!/usr/bin/env bash
# Looper launcher — starts the server if not running, then opens the browser
INSTALL_DIR="$INSTALL_DIR"
PYTHON="\$INSTALL_DIR/.venv/bin/python"
LOG="\$INSTALL_DIR/server.log"
PORT=$PORT

# Load nvm if present (needed when Node/n8n was installed via nvm)
export NVM_DIR="\$HOME/.nvm"
[ -s "\$NVM_DIR/nvm.sh" ] && source "\$NVM_DIR/nvm.sh" --no-use

# Start server if not already listening
if ! curl -s --connect-timeout 1 "http://127.0.0.1:\$PORT" > /dev/null 2>&1; then
    nohup "\$PYTHON" "\$INSTALL_DIR/run.py" > "\$LOG" 2>&1 &
    echo "Starting Looper server..."
    for i in \$(seq 1 30); do
        sleep 0.5
        curl -s --connect-timeout 1 "http://127.0.0.1:\$PORT" > /dev/null 2>&1 && break
    done
fi

# Open browser — try common options in order
URL="http://localhost:\$PORT"
if command -v xdg-open &>/dev/null;        then xdg-open "\$URL"
elif command -v gnome-open &>/dev/null;    then gnome-open "\$URL"
elif command -v sensible-browser &>/dev/null; then sensible-browser "\$URL"
elif command -v firefox &>/dev/null;       then firefox "\$URL" &
elif command -v google-chrome &>/dev/null; then google-chrome "\$URL" &
elif command -v chromium-browser &>/dev/null; then chromium-browser "\$URL" &
else echo "Looper is running at \$URL — open it in your browser."
fi
LAUNCHER

chmod +x "$LAUNCHER"
log "Launcher: $LAUNCHER"

# Symlink to ~/. local/bin so 'looper' works from any terminal
mkdir -p "$BIN_DIR"
ln -sf "$LAUNCHER" "$BIN_DIR/looper"
log "Terminal command: looper  (make sure $BIN_DIR is in your PATH)"

# ── .desktop file content ──────────────────────────────────────────────────────
step "Creating application shortcuts"

DESKTOP_CONTENT="[Desktop Entry]
Version=1.0
Type=Application
Name=Looper
Comment=AI Company Platform — run AI agent hierarchies locally
Exec=$LAUNCHER
Icon=$ICON_PNG
Terminal=false
Categories=Office;Productivity;Utility;Development;
StartupNotify=true
StartupWMClass=looper
Keywords=AI;agents;automation;LLM;openrouter;"

# App menu entry
mkdir -p "$APP_DIR"
echo "$DESKTOP_CONTENT" > "$DESKTOP_FILE"
chmod +x "$DESKTOP_FILE"
log "App menu entry: $DESKTOP_FILE"

# Refresh app menu database
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$APP_DIR" 2>/dev/null || true
fi

# Desktop shortcut
if [ -d "$DESKTOP_DIR" ]; then
    echo "$DESKTOP_CONTENT" > "$DESKTOP_SHORTCUT"
    chmod +x "$DESKTOP_SHORTCUT"

    # Linux Mint / Cinnamon: mark as trusted so double-click launches it
    if command -v gio &>/dev/null; then
        gio set "$DESKTOP_SHORTCUT" "metadata::trusted" true 2>/dev/null || true
    fi
    # GNOME fallback
    if command -v dbus-launch &>/dev/null && command -v gio &>/dev/null; then
        dbus-launch gio set "$DESKTOP_SHORTCUT" "metadata::trusted" true 2>/dev/null || true
    fi
    log "Desktop shortcut: $DESKTOP_SHORTCUT"
else
    warn "No ~/Desktop directory found — skipping desktop shortcut."
fi

# ── PATH hint ─────────────────────────────────────────────────────────────────
# Add ~/.local/bin to PATH in shell config if not already there
for RC in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
    if [ -f "$RC" ] && ! grep -q '\.local/bin' "$RC" 2>/dev/null; then
        echo '' >> "$RC"
        echo '# Added by Looper installer' >> "$RC"
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$RC"
    fi
done

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GRN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GRN}║  Looper installed successfully!                      ║${NC}"
echo -e "${GRN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BLU}▶  From the app menu:${NC}  Search for \"Looper\""
echo -e "  ${BLU}▶  From the desktop:${NC}   Double-click the Looper icon"
echo -e "  ${BLU}▶  From a terminal:${NC}    looper   (or: source ~/.bashrc first)"
echo -e "  ${BLU}▶  Direct URL:${NC}         http://localhost:$PORT"
echo ""
echo "  Installed to: $INSTALL_DIR"
echo "  Server log:   $INSTALL_DIR/server.log"
echo ""
echo -e "  To uninstall: rm -rf \"$INSTALL_DIR\" \"$DESKTOP_FILE\" \"$DESKTOP_SHORTCUT\" \"$BIN_DIR/looper\""
echo ""
