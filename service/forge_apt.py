#!/usr/bin/env python3
"""THE FORGE: curated APT software centre for Comet's Debian Trixie rootfs."""
from __future__ import annotations
import argparse, fcntl, json, os, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import desktop_environment as desktop

# Entries are deliberately curated for ARM64/H700. No raw package name is ever
# accepted from UI input; unavailable upstream projects are displayed disabled.
CATALOG = (
("CORE","libevdev-dev","evdev development headers","Build native Linux controller and event-input integrations.","H700"),
("CORE","libinput-dev","libinput development files","Develop input-device discovery and event-handling components.","H700"),
("CORE","libudev-dev","udev development headers","Build applications that enumerate devices without managing host services.","H700"),
("CORE","libdrm-dev","DRM development files","Develop Linux display and buffer-management integrations.","GPU"),
("CORE","libgbm-dev","GBM development files","Develop graphics buffer allocation paths used by compositors.","GPU"),
("CORE","libegl1-mesa-dev","EGL development files","Build EGL applications and graphics integrations.","GPU"),
("CORE","libgl4es-dev","GL4ES development files","Compatibility layer for legacy OpenGL calls over GLES hardware.","GPU"),
("CORE","libwayland-dev","Wayland development files","Build native Wayland clients and compositor integrations.","WAYLAND"),
("CORE","wayland-protocols","Wayland protocols","Protocol definitions for Wayland application development.","WAYLAND"),
("CORE","libxkbcommon-dev","XKB development files","Keyboard layout and keymap support for Wayland/X11 applications.","INPUT"),
("CORE","libasound2-dev","ALSA development files","Build applications against the Linux ALSA audio API.","AUDIO"),
("CORE","libpulse-dev","PulseAudio development files","Build applications using PulseAudio client APIs.","AUDIO"),
("CORE","libsdl2-image-dev","SDL2 image development files","Load common image formats in SDL2-based handheld applications.","H700"),
("CORE","libsdl2-ttf-dev","SDL2 font development files","Render TrueType fonts in SDL2 applications.","H700"),
("CORE","libsdl2-mixer-dev","SDL2 mixer development files","Add audio mixing to SDL2 games and applications.","AUDIO"),
("INPUT","joystick","Joystick tools","Inspect SDL/Linux joystick devices.","INPUT"),
("INPUT","evtest","Input event monitor","Inspect raw Linux input events and controller buttons.","INPUT"),
("INPUT","inputattach","Serial input bridge","Attach supported serial input devices to Linux input.","INPUT"),
("INPUT","qjoypad","QJoyPad","Map controller buttons to keyboard and mouse actions. X11 only.","X11"),
("INPUT","libinput-tools","libinput diagnostics","Inspect touch, mouse, keyboard and pointer devices.","INPUT"),
("INPUT","xserver-xorg-input-libinput","Xorg libinput driver","Modern X11 input driver for keyboard and pointer devices.","X11"),
("INPUT","xserver-xorg-input-evdev","Xorg evdev driver","Fallback X11 input driver for handheld event devices.","X11"),
("DESKTOP","foot","Foot terminal","Fast Wayland-native terminal emulator.","WAYLAND"),
("DESKTOP","waybar","Waybar","Status bar for wlroots and labwc sessions.","WAYLAND"),
("DESKTOP","mako-notifier","Mako notifications","Lightweight notification daemon for Wayland.","WAYLAND"),
("DESKTOP","wofi","Wofi launcher","Application launcher for Wayland compositors.","WAYLAND"),
("DESKTOP","swaybg","Sway wallpaper","Wallpaper helper for Wayland compositors.","WAYLAND"),
("DESKTOP","xwayland","XWayland compatibility","Run selected X11 applications inside labwc.","WAYLAND"),
("DESKTOP","thunar","Thunar file manager","Lightweight GTK file manager for X11 desktop profiles.","X11"),
("DESKTOP","pcmanfm","PCManFM file manager","Lightweight file manager for LXDE and Openbox.","X11"),
("DESKTOP","xarchiver","Xarchiver","Lightweight archive manager for desktop sessions.","X11"),
("DEVELOPMENT","git","Git","Version control for source trees and project repositories.","H700"),
("DEVELOPMENT","curl","cURL","HTTP transfer tool and library.","H700"),
("DEVELOPMENT","wget","Wget","Download assets and source archives.","H700"),
("DEVELOPMENT","python3-venv","Python virtual environments","Create isolated Python environments for app tooling.","H700"),
("DEVELOPMENT","python3-pip","Python package installer","Install Python build dependencies inside Debian.","H700"),
("DEVELOPMENT","build-essential","C/C++ build toolchain","GCC, G++, make and standard development tools.","H700"),
("DEVELOPMENT","cmake","CMake","Cross-platform native build configuration.","H700"),
("DEVELOPMENT","ninja-build","Ninja","Fast incremental build system.","H700"),
("DEVELOPMENT","pkg-config","pkg-config","Discover native library compiler and linker flags.","H700"),
("DEVELOPMENT","libsdl2-dev","SDL2 development files","Headers and libraries for controller-first SDL applications.","H700"),
("DEVELOPMENT","libgl-dev","OpenGL development files","OpenGL headers and link-time development files.","GPU"),
("MEDIA","ffmpeg","FFmpeg","Audio/video conversion and inspection tools.","H700"),
("MEDIA","mpv","MPV player","Lightweight media player; hardware video decode is not guaranteed.","H700"),
("MEDIA","alsa-utils","ALSA utilities","Inspect and configure exposed host ALSA devices.","AUDIO"),
("MEDIA","pavucontrol","PulseAudio volume control","Volume and audio routing UI for X11 profiles.","X11"),
("MEDIA","sox","SoX audio tools","Record, inspect and convert audio files.","H700"),
("NETWORK","openssh-client","OpenSSH client","SSH, SCP and SFTP client tools.","H700"),
("NETWORK","rsync","Rsync","Synchronize project files across local and remote systems.","H700"),
("NETWORK","syncthing","Syncthing","Peer-to-peer file synchronization; autostart remains disabled.","SERVICE"),
("NETWORK","iputils-ping","Ping tools","Basic network reachability diagnostics.","H700"),
("UTILITIES","htop","Process monitor","Interactive process and memory monitor.","H700"),
("UTILITIES","btop","System monitor","Resource monitor with CPU, memory, disk and process views.","H700"),
("UTILITIES","jq","JSON processor","Inspect and transform JSON from muOS and applications.","H700"),
("UTILITIES","tree","Directory tree","Display project and filesystem trees.","H700"),
("UTILITIES","ncdu","Disk usage explorer","Find large directories and manage storage usage.","H700"),
("UTILITIES","unzip","ZIP extractor","Extract project and application archives.","H700"),
("UTILITIES","zip","ZIP creator","Create application and asset archives.","H700"),
("UTILITIES","file","File type detector","Inspect binaries and application assets.","H700"),
("UTILITIES","nano","Nano editor","Small terminal text editor.","H700"),
)
SPECIAL = (
("INPUT","input-leap","Input Leap","Share one keyboard and pointer between computers. Upstream Linux/Wayland support exists, but Debian Trixie ARM64 has no package in the configured APT repositories.","UPSTREAM ONLY"),
)
CATEGORIES = ("ALL","CORE","INPUT","DESKTOP","DEVELOPMENT","MEDIA","NETWORK","UTILITIES")

class ForgeError(RuntimeError): pass

def clean(value, limit=240):
    return str(value).replace("|","/").replace("\r"," ").replace("\n"," ").strip()[:limit]

def write_status(app_dir, state, percent, message, package=""):
    path=app_dir/"data"/"forge-operation.status"; path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(".tmp")
    with tmp.open("w",encoding="utf-8") as f:
        f.write("{}|{}|{}|{}\n".format(state,max(0,min(100,int(percent))),clean(message),clean(package,128)))
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp,path)

def write_catalog(app_dir, rows, message=""):
    path=app_dir/"data"/"forge-catalog.txt"; path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(".tmp")
    with tmp.open("w",encoding="utf-8") as f:
        f.write("META|{}|{}\n".format(int(time.time()),clean(message)))
        for r in rows:
            f.write("PKG|{}|{}|{}|{}|{}|{}|{}|{}\n".format(
                clean(r["category"],20),clean(r["package"],128),clean(r["title"],80),
                clean(r["summary"],160),"1" if r["installed"] else "0",
                "1" if r["available"] else "0",clean(r["size"],24),clean(r["tag"],24)))
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp,path)

def run(command, log, timeout=900, capture=False):
    try:
        r=subprocess.run(command,stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if capture else log,stderr=subprocess.STDOUT,
            text=capture,check=False,timeout=timeout)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise ForgeError("{}: {}".format(command[0],exc)) from exc
    if r.returncode != 0:
        detail=(r.stdout or "").strip()[-500:] if capture else ""
        raise ForgeError("{} failed ({}): {}".format(command[0],r.returncode,detail))
    return r

def locate(slot):
    if slot not in desktop.SLOTS: raise ForgeError("unknown storage slot")
    mounted,writable=desktop.mounted_slot(slot)
    if not mounted: raise ForgeError(slot.upper()+" is not mounted")
    if not writable: raise ForgeError(slot.upper()+" is mounted read-only")
    root=desktop.SLOTS[slot].resolve(strict=True)
    if root != desktop.SLOTS[slot] or not root.is_dir():
        raise ForgeError("selected storage root is not a trusted mount")
    stage=desktop.safe_staging_directory(root)
    image=stage/"debian.img"; marker=stage/".comet-debian-ready"
    if image.is_symlink() or marker.is_symlink(): raise ForgeError("refusing symbolic-link Debian image")
    try: manifest=json.loads(marker.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as exc:
        raise ForgeError("install Debian Trixie from Desktop System before using THE FORGE") from exc
    if manifest.get("distribution")!="debian" or manifest.get("codename")!="trixie" or not image.is_file():
        raise ForgeError("Debian Trixie root filesystem is not ready")
    return image

def query_catalog(mountpoint,log):
    names=[r[1] for r in CATALOG]
    fmt="-f="+chr(36)+"{binary:Package}|"+chr(36)+"{db:Status-Status}|"+chr(36)+"{Version}\n"
    result=run(["chroot",str(mountpoint),"/usr/bin/dpkg-query","-W",fmt],log,180,True)
    installed={}
    for line in (result.stdout or "").splitlines():
        p=line.split("|",2)
        if len(p)==3 and p[1]=="installed": installed[p[0].split(":",1)[0]]=p[2]
    result=run(["chroot",str(mountpoint),"/usr/bin/apt-cache","show"]+names,log,300,True)
    available={}; current={}
    for line in (result.stdout or "").splitlines()+[""]:
        if not line.strip():
            if current.get("Package") and current["Package"] not in available:
                available[current["Package"]]=current
            current={}; continue
        if ": " in line:
            k,v=line.split(": ",1)
            if k in ("Package","Version","Installed-Size","Size"): current[k]=v.strip()
    rows=[]
    for cat,pkg,title,summary,tag in CATALOG:
        meta=available.get(pkg,{})
        size=meta.get("Installed-Size","")
        try: size="{:.1f} MB".format(int(size)/1024) if size else ""
        except ValueError: size=""
        rows.append({"category":cat,"package":pkg,"title":title,"summary":summary,
                     "installed":pkg in installed,"available":bool(meta),
                     "size":size or ("installed" if pkg in installed else "—"),"tag":tag})
    for cat,pkg,title,summary,tag in SPECIAL:
        rows.append({"category":cat,"package":pkg,"title":title,"summary":summary,
                     "installed":False,"available":False,"size":"—","tag":tag})
    return rows

def with_rootfs(slot,app_dir,action,package=""):
    if os.geteuid()!=0: raise ForgeError("Comet's muOS application runner must provide root privileges")
    allowed={r[1] for r in CATALOG}
    if action in ("install","remove") and package not in allowed:
        raise ForgeError("package is not in the curated Comet catalogue")
    image=locate(slot); mountpoint=app_dir/"data"/"desktop-mnt"
    if mountpoint.is_symlink(): raise ForgeError("desktop mountpoint is a symbolic link")
    log_path=app_dir/"data"/"forge-apt.log"; log_path.parent.mkdir(parents=True,exist_ok=True)
    with log_path.open("ab") as log:
        manager=desktop.ImageMount(image,mountpoint,log)
        try:
            manager.mount_image()
            manager.bind_host_tree(share_storage=False)
            policy=mountpoint/"usr/sbin/policy-rc.d"; policy.parent.mkdir(parents=True,exist_ok=True)
            policy.write_text("#!/bin/sh\nexit 101\n",encoding="ascii"); policy.chmod(0o755)
            if action=="catalog":
                rows=query_catalog(mountpoint,log)
                write_catalog(app_dir,rows,"Debian Trixie APT // curated H700 catalogue")
                write_status(app_dir,"READY",100,"{} curated software entries".format(len(rows)))
                return 0
            if action=="update":
                write_status(app_dir,"UPDATING",5,"Refreshing Debian Trixie package indexes")
                desktop.run_apt_with_progress(
                    ["chroot",str(mountpoint),"/usr/bin/env","DEBIAN_FRONTEND=noninteractive",
                     "PATH=/usr/sbin:/usr/bin:/sbin:/bin","apt-get","-o","Acquire::Retries=2","update"],
                    log=log, timeout=1500,
                    on_progress=lambda percent,message: write_status(
                        app_dir,"UPDATING",5+int(percent*0.90),
                        message or "Refreshing Debian Trixie package indexes"),
                )
                rows=query_catalog(mountpoint,log); write_catalog(app_dir,rows,"Package lists refreshed")
                write_status(app_dir,"REFRESHED",100,"APT package indexes refreshed")
                return 0
            command="install" if action=="install" else "remove"
            write_status(app_dir,"INSTALLING" if action=="install" else "REMOVING",
                         10,command.title()+" "+package,package)
            operation_state = "INSTALLING" if action=="install" else "REMOVING"
            run_command = ["chroot",str(mountpoint),"/usr/bin/env","DEBIAN_FRONTEND=noninteractive",
                           "APT_LISTCHANGES_FRONTEND=none","PATH=/usr/sbin:/usr/bin:/sbin:/bin",
                           "apt-get","-o","Acquire::Retries=2","-o","Dpkg::Options::=--force-confold",
                           command,"-y","--no-install-recommends",package]
            desktop.run_apt_with_progress(
                run_command,log=log,timeout=2400,
                on_progress=lambda percent,message: write_status(
                    app_dir,operation_state,10+int(percent*0.85),
                    message or (command.title()+" "+package),package),
            )
            write_status(app_dir,"DONE",100,command.title()+" completed",package)
            rows=query_catalog(mountpoint,log); write_catalog(app_dir,rows,"Software inventory refreshed")
            return 0
        except Exception as exc:
            write_status(app_dir,"FAILED",0,str(exc),package); raise
        finally:
            try: (mountpoint/"usr/sbin/policy-rc.d").unlink(missing_ok=True)
            except OSError: pass
            if not manager.cleanup():
                write_status(app_dir,"CLEANUP_REQUIRED",0,"APT finished but Debian mounts need attention",package)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("catalog","update","install","remove"))
    parser.add_argument("--slot",required=True,choices=sorted(desktop.SLOTS))
    parser.add_argument("--package",default="")
    parser.add_argument("--app-dir",default=os.environ.get("COMET_DESK_APP_DIR",""))
    args=parser.parse_args()
    if not args.app_dir:
        print("COMET_DESK_APP_DIR is required",file=sys.stderr); return 2
    app_dir=Path(args.app_dir).resolve()
    lock_path=app_dir/"data"/"debian-system.lock"; lock_path.parent.mkdir(parents=True,exist_ok=True)
    with lock_path.open("a+") as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            write_status(app_dir,"BUSY",0,"Another APT operation is already running",args.package); return 1
        try: return with_rootfs(args.slot,app_dir,args.action,args.package)
        except (ForgeError,desktop.SetupError,OSError,subprocess.SubprocessError,json.JSONDecodeError) as exc:
            write_status(app_dir,"FAILED",0,str(exc),args.package)
            print("[the-forge] ERROR: {}".format(exc),file=sys.stderr); return 1
        finally:
            try: fcntl.flock(lock,fcntl.LOCK_UN)
            except OSError: pass

if __name__=="__main__": raise SystemExit(main())
