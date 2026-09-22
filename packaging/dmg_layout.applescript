on run argv
    set mountPath to item 1 of argv
    tell application "Finder"
        set volumeName to name of (POSIX file mountPath as alias)
        open disk volumeName
        set diskWindow to container window of disk volumeName
        set current view of diskWindow to icon view
        set toolbar visible of diskWindow to false
        set statusbar visible of diskWindow to false
        set bounds of diskWindow to {160, 120, 760, 470}
        set icon size of icon view options of diskWindow to 104
        set arrangement of icon view options of diskWindow to not arranged
        set position of item "Finviz Tracker.app" of disk volumeName to {165, 205}
        set position of item "Applications" of disk volumeName to {435, 205}
        close diskWindow
    end tell
end run
