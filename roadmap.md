# Ideas for re-structuring this lib

## OOP based model

- AtemConnection Class as master
- Several classes for handling of subaspects: "feature classes"
- Feature classes register function for handling messages from the switcher
- Feature classes provide functions for:
 - retrieving values
 - listen on value change
 - manipulating features
 - getting option lists for enum values

## Feature classes

- AtemFacts
 - version
 - topologies
 - power
 - etc.
- AtemMacros
 - controlling macros
- AtemConfig
 - down conversion
 - video standard
 - input properties
 - multiviewers
- AtemMixing
 - program and preview
 - cut/auto
 - FTB
 - transitions
 - ...
- AtemKeyerBase
 - AtemKeyer
 - AtemDownstreamKeyer
- AtemVirtualSource
 - AtemColorGen
 - AtemMediaplayer
- AtemMediaPool
- AtemAux
- AtemCameraControl
- AtemSuperSource
- AtemAudioMixer
- AtemTally
 - video tallies
 - audio tallies