# RNBO Minimal Export integration boundary

Status: `reference / source-required`.

RNBO Minimal Export is a host-side import path, not a Ksoloti DSP object. It is
therefore deliberately not advertised in the object catalog as something an AI
patch can instantiate.

A runnable importer requires a user-supplied RNBO Minimal Export package and
acceptance of its generated-code/runtime license. The bounded future pipeline
is:

1. accept one exported C++ package without modifying it;
2. inventory its audio, control, state, allocation, and external dependencies;
3. reject dynamic allocation, threads, filesystem access, or unbounded work;
4. generate a separate Object SDK wrapper and compatibility manifest;
5. run a host render comparison against the export;
6. attempt Cortex-M4 and H7 links independently; and
7. promote only the targets that actually compile, link, and profile.

This tag prevents a source-dependent integration from being mistaken for one
of the 19 runnable objects. The original comb and granular objects plus the
multi-object recipes cover the reusable Max/gen-style structures discussed for
this library without copying unlicensed workshop patchers.
