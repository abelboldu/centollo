#!/usr/bin/env python

import sys, os
import rpm
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
parser.add_option("-o", "--out", default="output.iso", dest="out", help="Output file (default: output.iso)")
parser.add_option("-p", "--packages", default="./packages",dest="packages", help="RPM packages directory")
parser.add_option("-c", "--comps", default="resources/comps.xml", dest="compsfile", help="comps.xml file")
parser.add_option("-s", "--splash", default="resources/splash.jpg", dest="isolinuxsplash", help="isolinux splash")

parser.add_option("-C", "--cfg", default="resources/isolinux.cfg", dest="isolinuxcfg", help="isolinux cfg")
parser.add_option("-n", "--name", default="", dest="name", help="System name")
parser.add_option("-v", "--version", default="", dest="version", help="System version")
parser.add_option("-b", "--bugs", default="", dest="bugs_url", help="Bugs url")
name version arch
parser.add_option("-I", "--implantmd5", action="store_true",dest="implantmd5", default=False, help="Implant iso md5")

(options, args) = parser.parse_args()

# Abort if iso is not specified
parser.check_required("-i")
parser.check_required("-o")

tmpdir = "/tmp/elsix"
tools = ["createrepo","xz","find","cpio","which","mkisofs","mksquashfs","rpm2cpio"]
updaterepo = True

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
  except:
    print("ERROR: Cannot create temporary folder "+tmpdir+"/iso")
    exit(3)

  # Mount loop
  try:
    call(["mount","-o","loop",options.isofile,tmpdir+"/iso"])
  except:
    print("ERROR: Couldn't mount ISO file "+isofile)
    exit(3)

  #
  # Copy ISO content
  #

  print("Copying ISO content...")
  try:
    call(["cp","-r",tmpdir+"/iso",tmpdir+"/newiso"])
  except:
    print("ERROR: Cannot copy ISO content to "+tmpdir+"/iso")
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
    except:
      print("ERROR: Cannot copy extra packages.")
      exit(3)   
  
  # Add boot files
  print("Copying isolinux splash...")
  if os.path.isdir(options.isolinuxsplash):
    call(["cp",options.isolinuxsplash,tmpdir+"/newiso/isolinux"])
  else:
    print("WARNING: Cannot copy boot splash.")
  # grub customized in redhat-logos
    
  print("Copying isolinux.cfg...")
  if os.path.isdir(options.isolinuxcfg):
    call(["cp",options.isolinuxcfg,tmpdir+"/newiso/isolinux"])
  else:
    print("WARNING: Cannot copy isolinux.cfg")

  # Update yum repo
  if updaterepo:
    print("Updating packages repository...")
    try:
      call(["cd",tmpdir+"/newiso","&&","createrepo","-g","repodata/comps.xml","."])
    except:
      print("WARNING: Cannot create repository")
  else:
    print("Not updating packages repository.")

  # Custom initrd
  print("Branding initrd...")
  try:
    call(["mkdir","-p",tmpdir+"/initrd.dir"])
    # Unpack
    call(["cd",tmpdir+"/initrd.dir","&&","xz","--decompress","--format=lzma","--stout",tmpdir+"newiso/isolinux/initrd.img",
          "|","cpio","--quiet","--iudm"])
    # Brand .buildstamp
    branding(tmpdir+"/initrd.dir/.buildstamp",options.name,options.version,options.bugs_url,options.arch)
    # Repack
    call(["cd",tmpdir+"/initrd.dir","&&","find","./","|","cpio","--quiet","-H","newc","-o",
          "|","xz","--format=lzma",">",tmpdir+"/newiso/isolinux/initrd.img"])
    # Cleanup
    if options.cleanup:
      call(["rm","-rf",tmpdir+"/initrd.dir"])
  except:
    print("ERROR: Cannot brand initrd")
    exit(3)


  # Custom stage2
  print("Branding install.img...")
  try:
    call(["mkdir","-p",tmpdir+"/initrd.dir"])
    # Unpack
    call(["cd",tmpdir+"/initrd.dir","&&","xz","--decompress","--format=lzma","--stout",tmpdir+"newiso/isolinux/initrd.img",
          "|","cpio","--quiet","--iudm"])
    # Brand .buildstamp
    branding(tmpdir+"/initrd.dir/.buildstamp",options.name,options.version,options.bugs_url,options.arch)
    # Repack
    call(["cd",tmpdir+"/initrd.dir","&&","find","./","|","cpio","--quiet","-H","newc","-o",
          "|","xz","--format=lzma",">",tmpdir+"/newiso/isolinux/initrd.img"])
    # Cleanup
    if options.cleanup:
      call(["rm","-rf",tmpdir+"/initrd.dir"])
  except:
    print("ERROR: Cannot brand initrd")
    exit(3) 
  # Custom release notes
  # Create ISO
  # Implant md5
  # Cleanup

if __name__ == "__main__":
  before = time.time()
  main()
  after = time.time()
  print("SUCCESS! ISO generation took: "+str((after-before)/60)+" minutes.")
