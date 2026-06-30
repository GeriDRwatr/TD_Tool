# TDTool — Інструкція для встановлення на Linux

Переглядач і редактор PDF: перегляд, зміна порядку сторінок,
розбивка документа на кілька файлів за групами.

---

## Зміст

1. [Швидкий запуск (3 команди)](#варіант-1-запуск-без-встановлення-найпростіший)
2. [Встановлення як системний додаток](#варіант-2-встановлення-як-системний-додаток)
   - [AppImage — будь-який дистрибутив](#appimage--будь-який-linux-дистрибутив)
   - [.deb — Ubuntu / Debian / Mint](#deb--ubuntu--debian--linux-mint)
   - [.rpm — Fedora / RHEL / openSUSE](#rpm--fedora--rhel--opensuse)
3. [Видалення](#видалення)
4. [Вирішення проблем](#вирішення-проблем)

---

## Варіант 1: Запуск без встановлення (найпростіший)

Не потребує прав адміністратора. Достатньо мати Python 3.10+.

### 1.1 Перевір Python

```bash
python3 --version   # потрібно 3.10 або новіше
```

Якщо Python відсутній:

```bash
# Ubuntu / Debian / Mint
sudo apt install python3 python3-pip python3-venv

# Fedora / RHEL
sudo dnf install python3 python3-pip

# Arch / Manjaro
sudo pacman -S python python-pip
```

### 1.2 Розпакуй архів і перейди в папку

```bash
unzip TDTool_linux.zip
cd TDTool_linux
```

### 1.3 Встанови залежності та запусти

**Рекомендовано** — через віртуальне середовище (ізольовано, не зачіпає систему):

```bash
python3 -m venv venv
source venv/bin/activate
pip install PySide6 PyMuPDF
python3 main.py
```

**Або напряму** (без venv):

```bash
pip install --user PySide6 PyMuPDF
python3 main.py
```

> На Ubuntu 23.04+ pip може показати попередження "externally-managed-environment".
> Використай `pip install --break-system-packages PySide6 PyMuPDF` або venv (рекомендовано).

### 1.4 Відкрити PDF одразу з командного рядка

```bash
python3 main.py /шлях/до/документа.pdf
```

---

## Варіант 2: Встановлення як системний додаток

Після встановлення додаток з'явиться в меню програм і стане доступний у
**"Відкрити за допомогою"** для PDF-файлів.

### Передумови (один раз)

```bash
# Ubuntu / Debian / Mint
sudo apt install python3 python3-pip dpkg curl libfuse2

# Fedora / RHEL
sudo dnf install python3 python3-pip rpm-build curl fuse fuse-libs

# Встанови Python-залежності
pip install PySide6 PyMuPDF pyinstaller pyinstaller-hooks-contrib
```

### Збери пакет

```bash
cd TDTool_linux

# Зібрати всі формати одночасно:
bash linux/build.sh

# Або лише потрібний формат:
bash linux/build.sh --appimage   # universal AppImage
bash linux/build.sh --deb        # тільки .deb
bash linux/build.sh --rpm        # тільки .rpm
```

Готові файли з'являться в папці `dist_linux/`.

> **Іконка:** Якщо хочеш власну іконку — поклади PNG 256×256 як `linux/tdtool.png`
> перед збіркою. Якщо файл відсутній, скрипт автоматично генерує однокольоровий placeholder.

---

### AppImage — будь-який Linux дистрибутив

AppImage — самодостатній файл, не потребує встановлення.

```bash
# Після збірки:
chmod +x dist_linux/TDTool-1.0.0-x86_64.AppImage
./dist_linux/TDTool-1.0.0-x86_64.AppImage
```

**Інтеграція з робочим столом** (щоб з'явився в меню програм):

```bash
# Скопіювати в зручне місце (наприклад ~/Applications)
mkdir -p ~/Applications
cp dist_linux/TDTool-1.0.0-x86_64.AppImage ~/Applications/

# Встановити desktop entry вручну
cp linux/tdtool.desktop ~/.local/share/applications/
# Виправити шлях у .desktop файлі:
sed -i "s|Exec=tdtool|Exec=$HOME/Applications/TDTool-1.0.0-x86_64.AppImage|" \
    ~/.local/share/applications/tdtool.desktop
update-desktop-database ~/.local/share/applications/
```

---

### .deb — Ubuntu / Debian / Linux Mint

```bash
# Встановити
sudo dpkg -i dist_linux/tdtool_1.0.0_amd64.deb

# Якщо dpkg повідомить про відсутні залежності:
sudo apt install -f
```

Після встановлення:
- Команда `tdtool` доступна з терміналу
- Запис з'являється в меню програм
- PDF-файли можна відкривати через "Відкрити за допомогою → TDTool"

---

### .rpm — Fedora / RHEL / openSUSE

```bash
# Fedora / RHEL
sudo rpm -i dist_linux/tdtool-1.0.0-1.x86_64.rpm

# openSUSE
sudo zypper install dist_linux/tdtool-1.0.0-1.x86_64.rpm
```

---

## Видалення

| Спосіб встановлення | Команда видалення |
|---------------------|-------------------|
| Запуск із джерела   | Просто видали папку `TDTool_linux/` |
| AppImage            | Видали `.AppImage` файл і `~/.local/share/applications/tdtool.desktop` |
| .deb                | `sudo apt remove tdtool` |
| .rpm                | `sudo rpm -e tdtool` |

---

## Вирішення проблем

### «python3: command not found»
```bash
sudo apt install python3        # Ubuntu/Debian
sudo dnf install python3        # Fedora
```

### «No module named 'PySide6'»
```bash
pip install --user PySide6 PyMuPDF
# або якщо використовував venv:
source venv/bin/activate
pip install PySide6 PyMuPDF
```

### Додаток запускається, але вікно не з'являється (Wayland)
```bash
QT_QPA_PLATFORM=xcb python3 main.py
```
Або додай у `.desktop` файл рядок:
```
Exec=env QT_QPA_PLATFORM=xcb tdtool %f
```

### Помилка «libGL.so.1: cannot open shared object file»
```bash
# Ubuntu/Debian
sudo apt install libgl1

# Fedora
sudo dnf install mesa-libGL
```

### Помилка «libxcb-cursor.so.0: cannot open shared object file»
```bash
sudo apt install libxcb-cursor0    # Ubuntu/Debian
sudo dnf install xcb-util-cursor   # Fedora
```

### Помилка «FUSE» при запуску AppImage
```bash
sudo apt install libfuse2    # Ubuntu 22.04+
```
Або запусти без FUSE:
```bash
./TDTool-1.0.0-x86_64.AppImage --appimage-extract-and-run
```

---

## Системні вимоги

| Параметр | Мінімум |
|----------|---------|
| ОС | Linux з X11 або Wayland |
| Архітектура | x86_64 (amd64) |
| Python | 3.10+ |
| RAM | 256 МБ |
| Диск | 350 МБ (із залежностями) |

Перевірено на: Ubuntu 22.04, Ubuntu 24.04, Fedora 40, Debian 12.
