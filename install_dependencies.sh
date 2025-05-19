#!/bin/bash

# Salir inmediatamente si un comando falla
set -e

# Función para comprobar si el script se ejecuta como root
check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        echo "Este script necesita ser ejecutado como root o con sudo."
        echo "Ejemplo: sudo ./install_dependencies.sh"
        exit 1
    fi
    echo "Ejecutando con privilegios de root."
}

# Función para detectar la distribución
detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        # Usar $ID como identificador principal, $ID_LIKE como fallback
        CURRENT_DISTRO_ID=$ID
        CURRENT_DISTRO_ID_LIKE=$ID_LIKE
        echo "Distribución detectada (ID): $CURRENT_DISTRO_ID"
        if [ -n "$CURRENT_DISTRO_ID_LIKE" ]; then
            echo "Distribución similar a (ID_LIKE): $CURRENT_DISTRO_ID_LIKE"
        fi
    else
        # Fallback si /etc/os-release no existe (muy raro en sistemas modernos)
        if command -v lsb_release &> /dev/null; then
            CURRENT_DISTRO_ID=$(lsb_release -si | tr '[:upper:]' '[:lower:]')
        elif [ -f /etc/debian_version ]; then
            CURRENT_DISTRO_ID="debian" # Podría ser Ubuntu o un derivado
        elif [ -f /etc/fedora-release ]; then
            CURRENT_DISTRO_ID="fedora"
        elif [ -f /etc/arch-release ]; then
            CURRENT_DISTRO_ID="arch"
        elif [ -f /etc/SuSE-release ] || [ -f /etc/SUSE-brand ]; then # SUSE-brand para SLES/openSUSE más recientes
            CURRENT_DISTRO_ID="opensuse"
        else
            echo "No se pudo determinar la distribución automáticamente."
            echo "Por favor, instala las dependencias manualmente."
            exit 1
        fi
        echo "Distribución detectada (fallback): $CURRENT_DISTRO_ID"
    fi
}

# Función para instalar paquetes
install_packages() {
    local pm_update=""
    local pm_install=""
    local pkgs_python_tk=""
    local pkgs_grub_bios="" # Para MBR/BIOS
    local pkgs_tools=""     # parted, dosfstools, util-linux

    pkgs_tools="parted dosfstools util-linux" # Comunes en la mayoría de los casos

    # Determinar gestor de paquetes y nombres de paquetes
    # Se prioriza $CURRENT_DISTRO_ID, luego se intenta con $CURRENT_DISTRO_ID_LIKE

    distro_check="${CURRENT_DISTRO_ID:-unknown}"
    distro_like_check="${CURRENT_DISTRO_ID_LIKE:-unknown}"

    # Debian, Ubuntu, Mint, Pop!_OS, Zorin, Elementary, Kali, Parrot, MX Linux, Devuan, etc.
    if [[ "$distro_check" == "debian" || \
          "$distro_check" == "ubuntu" || \
          "$distro_check" == "linuxmint" || \
          "$distro_check" == "pop" || \
          "$distro_check" == "zorin" || \
          "$distro_check" == "elementary" || \
          "$distro_check" == "kali" || \
          "$distro_check" == "parrot" || \
          "$distro_check" == "mx" || \
          "$distro_check" == "devuan" || \
          echo "$distro_like_check" | grep -qE "debian|ubuntu" ]]; then
        echo "Configurando para familia Debian/Ubuntu..."
        pm_update="apt-get update"
        pm_install="apt-get install -y"
        pkgs_python_tk="python3 python3-tk"
        pkgs_grub_bios="grub-pc" # Instala GRUB2 para BIOS/MBR

    # Fedora, RHEL, CentOS, AlmaLinux, Rocky Linux, Oracle Linux
    elif [[ "$distro_check" == "fedora" || \
            "$distro_check" == "rhel" || \
            "$distro_check" == "centos" || \
            "$distro_check" == "almalinux" || \
            "$distro_check" == "rocky" || \
            "$distro_check" == "ol" || \
            echo "$distro_like_check" | grep -qE "fedora|rhel|centos" ]]; then
        echo "Configurando para familia Fedora/RHEL..."
        if command -v dnf &> /dev/null; then
            pm_install="dnf install -y"
        elif command -v yum &> /dev/null; then
            # yum-utils provee 'yum-config-manager', no es el gestor de paquetes principal
            # yum es el gestor en sistemas más antiguos
            pm_install="yum install -y"
        else
            echo "Error: Ni DNF ni YUM encontrados en sistema tipo Fedora/RHEL."
            exit 1
        fi
        pkgs_python_tk="python3 python3-tkinter"
        pkgs_grub_bios="grub2-pc grub2-tools" # grub2-tools para grub2-install

    # openSUSE (Tumbleweed, Leap), SLES
    elif [[ "$distro_check" == "opensuse-tumbleweed" || \
            "$distro_check" == "opensuse-leap" || \
            "$distro_check" == "opensuse" || \
            "$distro_check" == "sles" || \
            echo "$distro_like_check" | grep -qE "suse" ]]; then
        echo "Configurando para familia openSUSE..."
        pm_install="zypper install -y --no-recommends"
        pkgs_python_tk="python3-tk" # Generalmente python3-tk, podría ser versionado. zypper debe resolverlo.
        pkgs_grub_bios="grub2-i386-pc" # Para BIOS/MBR

    # Arch Linux, Manjaro, EndeavourOS, Garuda, Artix
    elif [[ "$distro_check" == "arch" || \
            "$distro_check" == "manjaro" || \
            "$distro_check" == "endeavouros" || \
            "$distro_check" == "garuda" || \
            "$distro_check" == "artix" || \
            echo "$distro_like_check" | grep -qE "arch" ]]; then
        echo "Configurando para familia Arch Linux..."
        pm_install="pacman -S --noconfirm --needed"
        pkgs_python_tk="python tk" # 'tk' es el paquete para Tkinter
        pkgs_grub_bios="grub"      # El paquete 'grub' en Arch es GRUB2

    # Alpine Linux
    elif [[ "$distro_check" == "alpine" ]]; then
        echo "Configurando para Alpine Linux..."
        pm_update="apk update"
        pm_install="apk add"
        pkgs_python_tk="python3 py3-tkinter"
        pkgs_grub_bios="grub-bios" # Específico para BIOS/MBR

    # Void Linux
    elif [[ "$distro_check" == "void" ]]; then
        echo "Configurando para Void Linux..."
        pm_update="xbps-install -S" # Sincroniza repositorios
        pm_install="xbps-install -y"
        pkgs_python_tk="python3 python3-tkinter"
        pkgs_grub_bios="grub-i386-pc" # Para BIOS/MBR
    else
        echo "Distribución '$CURRENT_DISTRO_ID' (ID_LIKE: '$CURRENT_DISTRO_ID_LIKE') no soportada automáticamente por este script."
        echo "Por favor, instala manualmente las siguientes dependencias o sus equivalentes para tu sistema:"
        echo "  - Python 3"
        echo "  - Tkinter para Python 3 (ej: python3-tk, python3-tkinter, tk)"
        echo "  - GRUB para BIOS/MBR (ej: grub-pc, grub2-pc, grub2-i386-pc, grub, grub-bios)"
        echo "  - parted"
        echo "  - dosfstools (para mkfs.vfat/mkfs.fat)"
        echo "  - util-linux (para lsblk, partprobe, etc.)"
        exit 1
    fi

    local all_packages="$pkgs_python_tk $pkgs_grub_bios $pkgs_tools"
    echo "Dependencias a instalar (o verificar): $all_packages"

    # Ejecutar actualización del gestor de paquetes (si es necesario)
    if [ -n "$pm_update" ]; then
        echo "Actualizando la lista de paquetes..."
        if $pm_update; then
            echo "Lista de paquetes actualizada."
        else
            echo "Advertencia: Falló la actualización de la lista de paquetes. Intentando continuar..."
        fi
    fi

    # Instalar los paquetes
    echo "Instalando dependencias..."
    if $pm_install $all_packages; then
        echo "Dependencias instaladas/verificadas con éxito."
    else
        echo "Error: Falló la instalación de uno o más paquetes."
        echo "Por favor, revisa los errores e intenta instalar manualmente: $all_packages"
        exit 1
    fi
}

# --- Inicio del Script ---
echo "=== Script de Instalación de Dependencias para USB Multiboot ==="
check_root
detect_distro
install_packages

echo ""
echo "---------------------------------------------------------------------"
echo "Instalación de dependencias completada."
echo "Ahora puedes intentar ejecutar la aplicación Python, por ejemplo:"
echo "  python3 Multiboot.py"
echo "Recuerda que la aplicación Python también debe ejecutarse con sudo:"
echo "  sudo python3 Multiboot.py"
echo "---------------------------------------------------------------------"

exit 0
