================================================================================
  MBS FILE TOOLS (Windows programs)
================================================================================

If you found this note next to some small programs (FName, FList, FNamePro,
FUndo), here is what they are for, in plain language.

These tools are for people who work with engineering drawing files (for example
PDF or CAD files) that use our standard document reference in the file name.
They only look at the folder they are saved in. They do not send your files
anywhere over the internet.

The "document reference" is the coded part at the start of a file name. It is
made of several short pieces separated by dashes, then the file extension.
For example, a drawing might end up named like this:

  R459-MBS-CZ-ZZ-DR-W-51457.pdf

Real names are often longer because people add a title or revision after the
reference (for example " ... - BLOCK C VENTILATION LAYOUT.pdf"). These tools
help pull out or standardise the reference part so names match our filing rules.

--------------------------------------------------------------------------------
  WHAT EACH PROGRAM DOES
--------------------------------------------------------------------------------

  FName
    Tidies file names in this folder so they follow the standard document
    reference style. It writes a short text report (FNameReport.txt) so you
    can see what it did.

  FList
    Does not rename anything. It writes a text list (filelist.txt) describing
    the files in this folder in a way that is easy to copy into a spreadsheet
    or email.

  FNamePro
    Like FList, but it also renames files to the standard document reference
    where it can. It writes a text report (report.txt) with more detail.

  FUndo
    Tries to put file names back how they were before FName or FNamePro was
    run. It reads the text reports those programs left in the same folder
    (including older copies named with -1, -2, and so on). You normally do
    not need it unless something went wrong or you change your mind.

If you run a program more than once, new report files may be named with -1,
-2, and so on so earlier reports are not lost.

--------------------------------------------------------------------------------
  MORE INFORMATION
--------------------------------------------------------------------------------

  Source code and full documentation (for IT or technical staff):
  https://github.com/Optimodo/mbs-file-tools

--------------------------------------------------------------------------------
  CONTACT
--------------------------------------------------------------------------------

  Mike McLean
  mike.mclean@malcolmbuildingservices.co.uk

================================================================================
  Tip: Keep this text file in the same folder as the programs so others know
  what they are for.
================================================================================
