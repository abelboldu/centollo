#!/usr/bin/env python

import sys, os
import rpm
from subprocess import call
import time
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
parser.add_option("-i", "--iso", dest="isofile", help="input iso file")

parser.add_option("-o", "--out", default="output.iso", dest="out", help="Output file (default: output.iso)")
parser.add_option("-I", "--implantmd5", action="store_true",dest="implantmd5", default=False, help="Implant iso md5")

(options, args) = parser.parse_args()

# Abort if iso is not specified
# parser.check_required("-i")

tmpdir = "/tmp/elsix"
tools = ["createrepo","xz","find","cpio","which","mkisofs","mksquashfs","rpm2cpio"]
updaterepo = True

def getRPMInfo(rpmPath):
  ts = rpm.ts()
  try:
    fdno = os.open(rpmPath, os.O_RDONLY)
    hdr = ts.hdrFromFdno(fdno)
    os.close(fdno)
  except:
    return False

  rpmInfo = {}
  rpmInfo['name'] = hdr['name']
  rpmInfo['summary'] = hdr['summary']
  rpmInfo['description'] = hdr['description']
  rpmInfo['release'] = hdr['release']
  rpmInfo['version'] = hdr['version']
  rpmInfo['arch'] = hdr['arch']
  rpmInfo['epoch'] = hdr['epoch']
  rpmInfo['buildtime'] = hdr['buildtime']
  rpmInfo['size'] = hdr['size']
  rpmInfo['archivesize'] = hdr['archivesize']

  return rpmInfo

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

def main:

  #
  # Inital checks
  #

  # Check required tools
  for tool in tools:
    if not which(t):
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
    call(["mount","-o","loop",isofile,tmpdir+"/iso"])
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
  if os.path.isfile(compsfile):
    call(["cp",compsfile,tmpdir+"/newiso/repodata/"])
  else:
    updaterepo = False
    print("WARNING: Not updating comps.xml")

  # Add extra packages
  
  # Add grub splash
  # Add isolinux splash
  # Add isolinux boot msg
  # Add isolinux options
  # Update yum repo
  # Custom initrd
  # Custom stage2
  # Custom release notes
  # Create ISO
  # Implant md5
  # Cleanup



if __name__ == "__main__":
  before = time.time()
  main(session)
  after = time.time()
  print("SUCCESS! ISO generation took: "+((after-before)/60)+" minutes.")
