from bisect import bisect_left

def take_closest(myList, myNumber):
    """
    Assumes myList is sorted. Returns closest value to myNumber.

    If two numbers are equally close, return the smallest number.
    """
    pos = bisect_left(myList, myNumber)
    if pos == 0:
        return myList[0]
    if pos == len(myList):
        return myList[-1]
    before = myList[pos - 1]
    after = myList[pos]
    if after - myNumber < myNumber - before:
        return after
    else:
        return before


import os, glob

icons = glob.glob("AppIcons/*.png")


iconList = {}

iconIDs  = []

for icon in icons:
    ID = int( icon.split('/')[-1].split('.')[0] )

    iconList[ID] = icon
    iconIDs.append(ID)


def getIcon(temp: int, isTray:bool = False) -> str:
    ico = iconList[ take_closest(iconIDs, temp/100) ]
    if isTray: ico = ico.replace('AppIcons', 'TrayIcons')
    return ico


    


if __name__ == "__main__":
    print( getIcon(1500) )
    print( getIcon(2000) )
    print( getIcon(4250) )
    print( getIcon(6500) )