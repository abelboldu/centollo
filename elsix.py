#!/usr/bin/env python

import sys, os
import dircache
from subprocess import call
import time, datetime
from optparse import OptionParser

class MyOptionParser(OptionParser):
  def error(self,msg):
    print msg
    sys.exit(3)
  def check_required(self, opt):
    option=self.get_option(opt)
    if getattr(self.values, option.dest) is None:
      self.error("%s option not supplied" % option)
  def check_under(self, opt1, opt2):
    option1=self.get_option(opt1)
    option2=self.get_option(opt2)
    if ( getattr(self.values, option1.dest) > getattr(self.values, option2.dest)):
      self.error("%s must be under or equal %s" % (option1,option2) )

parser = MyOptionParser(description="elsix ISO builder")
parser.add_option("-i", "--iso", dest="isofile", help="Input iso file")
parser.add_option("-o", "--out", default="output.iso", dest="output", help="Output file (default: output.iso)")
parser.add_option("-p", "--packages", default="./packages",dest="packages", help="RPM packages directory")
parser.add_option("-c", "--comps", default="resources/comps.xml", dest="compsfile", help="comps.xml file")
parser.add_option("-s", "--splash", default="resources/splash.jpg", dest="isolinuxsplash", help="isolinux splash")
parser.add_option("-C", "--cfg", default="resources/isolinux.cfg", dest="isolinuxcfg", help="isolinux cfg")
parser.add_option("-n", "--name", default="", dest="name", help="System name")
parser.add_option("-v", "--version", default="", dest="version", help="System version")
parser.add_option("-b", "--bugs", default="", dest="bugs_url", help="Bugs url")
parser.add_option("-a", "--anaconda", default="", dest="anaconda", help="Custom anaconda package")
parser.add_option("-l", "--redhatlogos", default="", dest="redhatlogos", help="Custom anaconda package")
parser.add_option("-r", "--relnotes", default="resources/release-notes", dest="relnotes", help="Custom anaconda package")
parser.add_option("--implantmd5", action="store_true",dest="implantmd5", default=False, help="Implant iso md5")
parser.add_option("--clean", action="store_true",dest="cleanup", default=False, help="Clean environment.")


(options, args) = parser.parse_args()

# Abort if iso is not specified
parser.check_required("-i")
parser.check_required("-o")

tmpdir = "/tmp/elsix"
tools = ["createrepo","xz","find","cpio","which","mkisofs","mksquashfs","rpm2cpio"]


def check_root():
  """ returns True if user is root, false otherwise """
  if os.getenv('LOGNAME','none').lower() == 'root':
    return True
  return False


def which(program):
  def is_exe(fpath):
    return os.path.isfile(fpath) and os.access(fpath, os.X_OK)
  fpath, fname = os.path.split(program)
  if fpath:
    if is_exe(program):
      return program
  else:
    for path in os.environ["PATH"].split(os.pathsep):
      exe_file = os.path.join(path, program)
      if is_exe(exe_file):
        return exe_file
  return None

def branding(file,product_name,product_version,bugs_url,arch):
    outfile = open(file,'w')
    outfile.write(datetime.datetime.now().strftime('%Y%m%d')+'0001.'+arch+"\n")
    outfile.write(product_name+"\n")
    outfile.write(product_version+"\n")
    outfile.write(bugs_url)
    outfile.close()

def main():

  updaterepo = True
  arch = 'x86_64'
  #
  # Inital checks
  #

  # Check required tools
  for tool in tools:
    if not which(tool):
      print("ERROR: "+tool+" not installed. Exiting.")
      exit(2)

  # Check root user
  if not check_root():
    print("Must be run as root.")
    exit(2)
  
  #
  # Prepare environment 
  #

  print("Setting up...")
  # Make tmp dir
  try:
    call(["mkdir","-p",tmpdir+"/iso"])
  except Exception, e:
    print("ERROR: Cannot create temporary folder "+tmpdir+"/iso")
    print e
    exit(3)

  # Mount loop
  try:
    call(["mount","-o","loop",options.isofile,tmpdir+"/iso"])
  except Exception, e:
    print("ERROR: Couldn't mount ISO file "+isofile)
    print e
    exit(3)

  #
  # Copy ISO content
  #

  print("Copying ISO content...")
  try:
    call(["cp","-r",tmpdir+"/iso",tmpdir+"/newiso"])
  except Exception, e:
    print("ERROR: Cannot copy ISO content to "+tmpdir+"/iso")
    print e
    exit(3)

  #
  # Copy repo config
  #

  print("Updating comps.xml...")
  if os.path.isfile(options.compsfile):
    call(["cp",options.compsfile,tmpdir+"/newiso/repodata/comps.xml"])
  else:
    updaterepo = False
    print("WARNING: Not updating comps.xml")

  # Add extra packages
  print("Copying extra packages...")
  if os.path.isdir(options.packages):
    try:
      call(["cp","-r",options.packages,tmpdir+"/newiso/Packages"])
    except Exception, e:
      print("ERROR: Cannot copy extra packages.")
      print e
      exit(3)   
  
  # Add boot files
  print("Copying isolinux splash...")
  if os.path.isfile(options.isolinuxsplash):
    call(["cp",options.isolinuxsplash,tmpdir+"/newiso/isolinux"])
  else:
    print("WARNING: Cannot copy boot splash.")
  # grub customized in redhat-logos
    
  print("Copying isolinux.cfg...")
  if os.path.isfile(options.isolinuxcfg):
    call(["cp",options.isolinuxcfg,tmpdir+"/newiso/isolinux"])
  else:
    print("WARNING: Cannot copy isolinux.cfg")

  # Update yum repo
  if updaterepo:
    print("Updating packages repository...")
    try:
      call(["cd",tmpdir+"/newiso","&&","createrepo","-g","repodata/comps.xml","."],shell=True)
    except Exception, e:
      print("ERROR: Cannot create repository")
      print e
      exit(3)
  else:
    print("Not updating packages repository.")

  # Custom initrd
  print("Branding initrd...")
  try:
    call(["mkdir","-p",tmpdir+"/initrd.dir"])
    # Unpack
    call(["cd",tmpdir+"/initrd.dir","&&","xz","--decompress","--format=lzma","--stout",tmpdir+"iso/isolinux/initrd.img",
          "|","cpio","--quiet","--iudm"],shell=True)
    # Brand .buildstamp
    branding(tmpdir+"/initrd.dir/.buildstamp",options.name,options.version,options.bugs_url,arch)
    # Repack
    call(["cd",tmpdir+"/initrd.dir","&&","find","./","|","cpio","--quiet","-H","newc","-o",
          "|","xz","--format=lzma",">",tmpdir+"/newiso/isolinux/initrd.img"],shell=True)
    # Cleanup
    if options.cleanup:
      call(["rm","-rf",tmpdir+"/initrd.dir"])
  except Exception, e:
    print("ERROR: Cannot brand initrd")
    print e
    exit(3)


  # Custom stage2
  print("Branding install.img...")
  try:
    call(["mkdir","-p",tmpdir+"/install.dir"])
    # Unpack
    call(["cd",tmpdir+"/install.dir","&&","unsquashfs",tmpdir+"iso/images/install.img"],shell=True)

    # Brand .buildstamp
    branding(tmpdir+"/install.dir/.buildstamp",options.name,options.version,options.bugs_url,arch)
    # Custom anaconda
    if options.anaconda and os.path.isfile(options.anaconda):
      call(["rm","-rf",tmpdir+"/install.dir/squashfs-root/usr/share/anaconda/pixmaps"])
      call(["cd",tmpdir+"/install.dir/squashfs-root/","&&","rpm2cpio",os.path.abspath(options.anaconda),"|","cpio","--quiet","-iud"],shell=True)

    # Custom redhat-logos
    if options.redhatlogos and os.path.isfile(options.redhatlogos):
      call(["cd",tmpdir+"/install.dir/squashfs-root/","&&","rpm2cpio",os.path.abspath(options.redhatlogos),"|","cpio","--quiet","-iud"],shell=True)

    # Repack
    call(["cd",tmpdir+"/install.dir","&&","mksquashfs","squashfs-root","install.img"],shell=True)
    call(["cd",tmpdir+"/install.dir","&&","mv","install.img",tmpdir+"/newiso/images/"],shell=True)

    if options.cleanup:
      call(["rm","-rf",tmpdir+"/initrd.dir"])
  except Exception, e:
    print("ERROR: Cannot brand install.img")
    print e
    exit(3) 

  # Custom release notes
  print("Copying release notes...")
  if os.path.isdir(options.relnotes):
    call(["cp","-r",options.relnotes+"/RELEASE-NOTES*",tmpdir+"/newiso/"])

  # Create ISO
  print("Creating ISO...")
  try:
    call(["mkisofs","-R","-J","-T","-b",tmpdir+"/newiso/isolinux/isolinux.bin","-c",tmpdir+"/newiso/isolinux/boot.cat",
          "-no-emul-boot","-boot-load-size","4","-boot-info-table","-o",options.output,"."],cwd=tmpdir+"/newiso",shell=True)
  except Exception, e:
    print("ERROR: Cannot create ISO")
    print e
    exit(3)

  # Implant md5
  # Cleanup

if __name__ == "__main__":
  before = time.time()
  main()
  after = time.time()
  print("SUCCESS! ISO generation took: "+str((after-before)/60)+" minutes.")
