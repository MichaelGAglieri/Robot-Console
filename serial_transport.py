# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Exclusive access to a user-selected serial port on macOS, Linux and Windows.

Never selects a port by itself. On macOS and Linux the port is a raw file descriptor
configured with termios (115200 8N1, no flow control), the code path tested on the
Mega. On Windows it is a pyserial object, opened exclusively by the system.
"""
import glob, os, re, subprocess, sys, time

WINDOWS = os.name == 'nt'
MACOS = sys.platform == 'darwin'
if not WINDOWS:
    import fcntl, select, struct, termios

# Arduino Mega 2560: ATmega16U2 (usbmodem / ttyACM) or CH340 / FTDI / CP210x clones.
MAC_PATTERNS = ('/dev/cu.usbmodem*', '/dev/cu.usbserial*', '/dev/cu.wchusbserial*', '/dev/cu.SLAB_USBtoUART*')
LINUX_PATTERNS = ('/dev/ttyACM*', '/dev/ttyUSB*')


def _windows_ports():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DEVICEMAP\SERIALCOMM')
    except OSError:
        return []
    ports = []
    try:
        index = 0
        while True:
            try:
                _name, value, _kind = winreg.EnumValue(key, index)
            except OSError:
                break
            if isinstance(value, str) and re.fullmatch(r'COM\d+', value):
                ports.append(value)
            index += 1
    finally:
        winreg.CloseKey(key)
    return sorted(set(ports), key=lambda p: int(p[3:]))


def candidate_ports():
    """Serial ports that may be the robot's board, in a stable order."""
    if WINDOWS:
        return _windows_ports()
    patterns = MAC_PATTERNS if MACOS else LINUX_PATTERNS
    return sorted({path for pattern in patterns for path in glob.glob(pattern)})


def looks_like_board(address):
    """Name check used for ports reported by arduino-cli; does not touch the device."""
    if WINDOWS:
        return bool(re.fullmatch(r'COM\d+', address or ''))
    patterns = MAC_PATTERNS if MACOS else LINUX_PATTERNS
    return any(address.startswith(p.rstrip('*')) for p in patterns)


def _aliases(port):
    aliases = [port]
    if port.startswith('/dev/cu.'):
        aliases.append('/dev/tty.' + port[8:])
    return [p for p in aliases if os.path.exists(p)]


def _owners_lsof(aliases):
    lsof = '/usr/sbin/lsof' if os.path.exists('/usr/sbin/lsof') else None
    if not lsof:
        from shutil import which
        lsof = which('lsof')
    if not lsof:
        return None
    try:
        result = subprocess.run([lsof, '-Fpc', '--', *aliases], capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ValueError('Impossibile verificare se la porta USB è libera.') from e
    if result.returncode not in (0, 1) or (result.returncode == 1 and result.stderr.strip()):
        raise ValueError('Impossibile verificare l’accesso alla porta USB: ' + result.stderr.strip()[:200])
    pid = None
    owners = []
    for line in result.stdout.splitlines():
        if line.startswith('p'):
            try:
                pid = int(line[1:])
            except ValueError:
                pid = None
        elif line.startswith('c') and pid is not None and pid != os.getpid():
            owners.append(line[1:] + ' (PID ' + str(pid) + ')')
    return owners


def _owners_proc(aliases):
    """Linux without lsof: processes of this user holding the device open."""
    targets = {os.path.realpath(p) for p in aliases}
    owners = []
    for fd_dir in glob.glob('/proc/[0-9]*/fd'):
        pid = int(fd_dir.split('/')[2])
        if pid == os.getpid():
            continue
        try:
            for entry in os.listdir(fd_dir):
                if os.path.realpath(os.path.join(fd_dir, entry)) in targets:
                    with open('/proc/%d/comm' % pid) as f:
                        owners.append(f.read().strip() + ' (PID ' + str(pid) + ')')
                    break
        except OSError:
            continue
    return owners


def ensure_port_available(port):
    """Refuse a port that disappeared or that another program keeps open."""
    if WINDOWS:
        if port not in _windows_ports():
            raise ValueError('Porta USB non più presente: seleziona la porta attuale della Mega.')
        return  # Windows opens COM ports exclusively: a busy port fails in open_port.
    aliases = _aliases(port)
    if not aliases:
        raise ValueError('Porta USB non più presente: seleziona la porta attuale della Mega.')
    owners = _owners_lsof(aliases)
    if owners is None:
        owners = _owners_proc(aliases) if os.path.isdir('/proc') else []
    if owners:
        raise ValueError('Porta USB occupata da ' + ', '.join(owners) + '. Chiudi il monitor seriale di Arduino o l’altro programma, poi riprova.')


def claim_exclusive(fd):
    try:
        fcntl.ioctl(fd, termios.TIOCEXCL)
    except OSError as e:
        raise ValueError('Impossibile ottenere l’accesso esclusivo alla porta USB.') from e


class WindowsPort:
    """Minimal pyserial wrapper with the same operations used on POSIX descriptors."""

    def __init__(self, port):
        try:
            import serial
        except ImportError as e:
            raise ValueError('Su Windows serve pyserial: python -m pip install pyserial') from e
        try:
            self.serial = serial.Serial(port=port, baudrate=115200, bytesize=8, parity='N', stopbits=1,
                                        timeout=0, write_timeout=1, rtscts=False, dsrdtr=False, xonxoff=False)
        except serial.SerialException as e:
            text = str(e)
            if 'Access is denied' in text or 'PermissionError' in text or 'Accesso negato' in text:
                raise ValueError('Porta USB occupata da un altro programma. Chiudi il monitor seriale di Arduino o l’altro programma, poi riprova.') from e
            raise ValueError('Impossibile aprire ' + port + ': ' + text[:200]) from e

    def write(self, data):
        try:
            self.serial.write(data)
        except Exception as e:  # pyserial raises SerialException/SerialTimeoutException
            raise OSError('USB scollegata') from e

    def read(self):
        try:
            waiting = self.serial.in_waiting
            return self.serial.read(min(waiting, 4096)) if waiting else None
        except Exception as e:
            raise OSError('USB scollegata') from e

    def set_lines(self, active):
        self.serial.dtr = active
        self.serial.rts = active

    def close(self):
        try:
            self.serial.close()
        except Exception:
            pass


def open_port(port):
    """Open and configure the port; returns an int descriptor (POSIX) or a WindowsPort."""
    if WINDOWS:
        handle = WindowsPort(port)
        handle.set_lines(True)
        return handle
    fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        claim_exclusive(fd)
        ensure_port_available(port)
        attr = termios.tcgetattr(fd)
        attr[0] = 0
        attr[1] = 0
        attr[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
        attr[3] = 0
        attr[4] = attr[5] = termios.B115200
        attr[6][termios.VMIN] = 0
        attr[6][termios.VTIME] = 0
        termios.tcsetattr(fd, termios.TCSANOW, attr)
        # Restore modem-control lines after avrdude; no ARM or motion command.
        set_lines(fd, True)
    except Exception:
        os.close(fd)
        raise
    return fd


def set_lines(handle, active):
    """Raise (True) or drop (False) DTR and RTS. Dropping then raising resets the Mega."""
    if isinstance(handle, WindowsPort):
        handle.set_lines(active)
        return
    lines = struct.pack('I', termios.TIOCM_DTR | termios.TIOCM_RTS)
    fcntl.ioctl(handle, termios.TIOCMBIS if active else termios.TIOCMBIC, lines)


def pulse_reset(handle, low=.12):
    set_lines(handle, False)
    time.sleep(low)
    set_lines(handle, True)


def write(handle, data):
    if isinstance(handle, WindowsPort):
        handle.write(data)
    else:
        os.write(handle, data)


def read(handle):
    """Bytes available now, None when there are none; OSError when the device is gone."""
    if isinstance(handle, WindowsPort):
        return handle.read()
    if not select.select([handle], [], [], 0)[0]:
        return None
    data = os.read(handle, 4096)
    if not data:
        raise OSError('USB scollegata')
    return data


def close(handle):
    if handle is None:
        return
    if isinstance(handle, WindowsPort):
        handle.close()
    else:
        try:
            os.close(handle)
        except OSError:
            pass
