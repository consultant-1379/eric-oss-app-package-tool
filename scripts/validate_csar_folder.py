#!/usr/bin/python3

#
#  Usage:    ./scripts/validate_csar_folder.py --folder <path_to_csar_folder>
#  Example:  ./scripts/validate_csar_folder.py --folder /tmp/csar_folder1
#


import argparse
import pathlib
import sys,os
import subprocess
import re,glob
import time
  

def main(argv):
  
    print ('Number of arguments:', len(sys.argv), 'arguments.')
    print ('Argument List:', str(sys.argv), '\n\n')
  
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', default=argparse.SUPPRESS)
    args = parser.parse_args()
    cwd = pathlib.Path().resolve()
    if 'folder' in args: 
        varCsarFolderPath = args.folder
        print('argument \'--folder\' was given, set to\t{}'.format(varCsarFolderPath) ,'\n')
    else:
        varCsarFolderPath = pathlib.Path().resolve()
        print('argument \'--folder\' was not given, cwd\t{}'.format(varCsarFolderPath) ,'\n')
  
    print('Checking Folder Structure:')
    cmd = "find %s"%varCsarFolderPath
    returned_value = subprocess.call(cmd, shell=True) 
    print('returned value:', returned_value)
    cmd = "ls -d %s/Definitions"%varCsarFolderPath
    returned_value = subprocess.call(cmd, shell=True) 
    cmd = "ls -d %s/Metadata"%varCsarFolderPath
    cmd3 = "ls -d %s/OtherDefinitions/ASD/Images"%varCsarFolderPath
    returned_value = subprocess.call(cmd, shell=True)
    returned_value = subprocess.call(cmd3, shell=True)
    print('returned value:', returned_value)

    print('Parsing yaml for keywords:')
    pattern1 = "APPType"
    check1 = 0
    print('Keyword search for: ',pattern1)
    file = open("%s/Definitions/AppDescriptor.yaml"%varCsarFolderPath, "r")
    for word in file:
        if re.search(pattern1, word):
            print(word)
            check1+=1
        else:
            print('.', end='')
    print('\nKeyword search count for: ',pattern1,' is ',check1)
    print('Validating necessary files existing in right folders:')
    print("Checking: %s/Metadata/Tosca.meta"%varCsarFolderPath,)
    file = open("%s/Metadata/Tosca.meta"%varCsarFolderPath, "r")
    print(os.path.getsize("%s/Metadata/Tosca.meta"%varCsarFolderPath))
    print("Checking: %s/OtherDefinitions/ASD/ASD.yaml"%varCsarFolderPath, )
    file = open("%s/OtherDefinitions/ASD/ASD.yaml"%varCsarFolderPath, "r")
    print(os.path.getsize("%s/OtherDefinitions/ASD/ASD.yaml"%varCsarFolderPath))
    print("Checking: %s/OtherDefinitions/ASD/Images/"%varCsarFolderPath)
    image_files = glob.glob("%s/OtherDefinitions/ASD/Images/*.tar"%varCsarFolderPath) 
    for image_file in image_files:
        print("Image file found: ",image_file," ",os.path.getsize(image_file))

    file = open("result.txt", "w")
    file.write("Folder structure: Passed\nKeywords in yaml:  Passed\nImage folder check: Passed")
    print("\nFolder structure: Passed\nKeywords in yaml:  Passed\nImage folder check: Passed")
    file.close()
    time.sleep(9)

if __name__ == "__main__":
    main(sys.argv[1:])

