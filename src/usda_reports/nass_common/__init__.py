"""Shared pieces of every report published through ESMIS / NASS (plan §4 'Generic NASS parser').

* :mod:`usda_reports.nass_common.esmis`: the ESMIS ``findByIdentifier`` client (0-based paging,
  file URLs only from ``files[]``, release dates from ``release_datetime``). WASDE uses it too.
* :mod:`usda_reports.nass_common.zipfetch`: download a release zip and read one member.
* :mod:`usda_reports.nass_common.csv_tables`: the NASS row-type grammar (``t/h/u/d/c/f``) of
  the ``*_all_tables.csv`` files inside NASS release zips.
"""
