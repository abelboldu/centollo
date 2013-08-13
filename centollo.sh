#!/bin/bash
#
# Centollo - Script for building CentOS based spins.
# Abel Boldú 2013 
#

NAME=Abiquo
VERSION=3.0
BUGS="http://support.abiquo.com"
ARCH=x86_64

BASEISO="./CentOS-6.4-x86_64-minimal.iso"
OUTPUT=abiquo-linux-$VERSION-preview-`date +%F-%H%M`.iso
PACKAGES="./packages"
ISOLINUXCFG="./resources/isolinux.cfg"
COMPS="./resources/comps.xml"
SPLASH="./resources/splash.jpg"
RELNOTES="./resources/release-notes*"
ANACONDA="./packages/anaconda-ee-13.21.195-1.el6.1.abiquo.x86_64.rpm"
RHLOGOS="./resources/abiquo-logos-ee-60.0.14-12.el6.abiquo.noarch.rpm"
ICONS="./resources/gnome-human.tar.gz"
COLOR="E5A843"

TOOLS=(createrepo xz find cpio which mkisofs mksquashfs rpm2cpio repomanage implantisomd5)

cleanup(){
echo "Cleaning up..."
umount $TMPDIR/iso &> /dev/null
rm -rf $TMPDIR &> /dev/null
}

# Check root
if [ "$(id -u)" != "0" ]; then
    echo "This script must be run as root" 1>&2
    exit 1
fi

# Check tools
for i in ${TOOLS[@]}
do 
    hash $i &> /dev/null
    if [ $? -eq 1 ];then
	echo "$i not found. Please install it."
	exit 1
    fi
done

echo "Setting up..."
START=$(date +%s)
CWD=`pwd`
TMPDIR=`mktemp -d --suffix=_cntll`
echo "Temporary directory: $TMPDIR"
mkdir $TMPDIR/iso
mount -o loop,ro $BASEISO $TMPDIR/iso
if [ $? -ne 0 ]; then
    echo "ERROR: Couldn't mount base ISO."
    cleanup
    exit 1
fi

echo "Copying ISO content..."
cp -r $TMPDIR/iso $TMPDIR/newiso
if [ $? -ne 0 ]; then
    echo "ERROR: Cannot copy ISO content."
    cleanup
    exit 1
fi

if [ -f $COMPS ]; then
    echo "Updating comps.xml..."
    rm -rf $TMPDIR/newiso/repodata
    mkdir $TMPDIR/newiso/repodata
    cp $COMPS $TMPDIR/newiso/repodata/comps.xml
    UPDATEREPO="yes"
else
    echo "WARNING: No comps.xml file"
fi

echo "Copying extra packages..."
cp -rf $PACKAGES/*.rpm $TMPDIR/newiso/Packages/

echo "Cleaning old packages..."
pushd $TMPDIR/newiso/Packages >& /dev/null
repomanage -o . | xargs rm -fr
popd >& /dev/null

if [ -n $UPDATEREPO ]; then
    echo "Updating repository..."
    pushd $TMPDIR/newiso/ >& /dev/null
    createrepo -g repodata/comps.xml .
    popd >& /dev/null
fi

echo "Copying isolinux.cfg..."
if [ -f $ISOLINUXCFG ];then
    cp $ISOLINUXCFG $TMPDIR/newiso/isolinux/isolinux.cfg
else
    echo "WARNING: Cannot copy isolinux.cfg"
fi

echo "Copying splash..."
if [ -f $SPLASH ];then
    cp $SPLASH $TMPDIR/newiso/isolinux/splash.jpg
else
    echo "WARNING: Cannot copy splash"
fi



echo "Branding initrd..."
mkdir -p $TMPDIR/newiso/initrd.dir
pushd $TMPDIR/newiso/initrd.dir >& /dev/null
xz --decompress --format=lzma --stdout $TMPDIR/iso/isolinux/initrd.img | cpio --quiet -iudm > /dev/null 2>&1
if [ $? -ne 0 ];then
    echo "ERROR: Failed to decompress initrd.img."
    cleanup
    exit 1
fi
echo `date +%Y%m%d`0001.$ARCH > .buildstamp
echo $NAME >> .buildstamp
echo $VERSION >> .buildstamp
echo $BUGS >> .buildstamp
find ./ | cpio --quiet -H newc -o | xz --format=lzma > $TMPDIR/newiso/isolinux/initrd.img 
if [ $? -ne 0 ];then
    echo "ERROR: Failed to compress initrd.img."
    cleanup
    exit 1
fi
cd ..
rm -rf initrd.dir
popd >& /dev/null

echo "Branding install.img (stage2)..."
mkdir -p $TMPDIR/newiso/install.dir
pushd $TMPDIR/newiso/install.dir >& /dev/null
unsquashfs $TMPDIR/iso/images/install.img >& /dev/null
if [ $? -ne 0 ];then
    echo "ERROR: Failed to extract install.img"
    cleanup
    exit 1
fi

echo `date +%Y%m%d`0001.$ARCH > .buildstamp
echo $NAME >> .buildstamp
echo $VERSION >> .buildstamp
echo $BUGS >> .buildstamp
popd >& /dev/null


if [ -f $ANACONDA ];then
    echo "Installing anaconda..."
    A_ANACONDA=`readlink -f $ANACONDA`
    pushd $TMPDIR/newiso/install.dir/squashfs-root >& /dev/null 
    # Previous clean
    rm -rf usr/share/anaconda/pixmaps
    rm -rf usr/lib/anaconda
    rm -rf $TMPDIR/newiso/images/updates.img
    rpm2cpio $A_ANACONDA | cpio --quiet -iud
    popd >& /dev/null
else
    echo "WARNING: Cannot install anaconda"
fi

echo "Customizing installer color..."
sed -i "s,86ABD9,$COLOR,g" $TMPDIR/newiso/install.dir/squashfs-root/usr/share/themes/Slider/gtk-2.0/gtkrc


if [ -f $RHLOGOS ];then
    echo "Installing redhat logos..."
    A_RHLOGOS=`readlink -f $RHLOGOS`
    pushd $TMPDIR/newiso/install.dir/squashfs-root >& /dev/null 
    rpm2cpio $A_RHLOGOS | cpio --quiet -iud
    popd >& /dev/null 
else
    echo "WARNING: Cannot install redhat logos"
fi

echo "Installing custom icons..."
if [ -f $ICONS ];then
    tar xf $ICONS -C $TMPDIR/newiso/install.dir/squashfs-root/usr/share/icons/gnome/
else
    echo "WARNING: Cannot install icons"
fi

echo "Recompressing install.img..."
pushd $TMPDIR/newiso/install.dir >& /dev/null
mksquashfs squashfs-root install.img >& /dev/null
if [ $? -ne 0 ];then
    echo "ERROR: Failed to create install.img"
    cleanup
    exit 1
fi
mv -f install.img $TMPDIR/newiso/images/
cd ..
rm -rf install.dir
popd >& /dev/null

echo "Installing release notes..."
cp $RELNOTES $TMPDIR/newiso/
if [ $? -ne 0 ];then
    echo "WARNING: Failed to copy release notes."
fi

echo "Creating ISO..."
pushd $TMPDIR/newiso/ >& /dev/null
mkisofs -joliet-long -T -b isolinux/isolinux.bin -c isolinux/boot.cat \
          -input-charset iso8859-1 -no-emul-boot -boot-load-size 4 -boot-info-table -R -m TRANS.TBL \
          -o $CWD/$OUTPUT  . >/dev/null 2>&1
popd >& /dev/null
if [ $? -ne 0 ];then
    echo "ERROR: Failed to build ISO."
    cleanup
    exit 1
fi

# Unmount and clean
cleanup

END=$(date +%s)
DIFF=$(( $END - $START ))
echo "Done!"
echo "It took $DIFF seconds to generate the ISO."

