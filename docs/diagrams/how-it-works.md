# How it works (diagram, parked)

This is the system-overview diagram pulled out of the main README on
2026-04-30. Saved here so it can be re-introduced later (probably with a
cleaner version) when the visual quality is up to launch standard.

```mermaid
flowchart TB
    subgraph Team["Your lab"]
        You[You]
        Mate[Lab member]
        Collab[Collaborator]
    end

    Team --> CC[Claude Code]
    CC --> VL[VaultLab capabilities]

    subgraph Memory["Centralized memory"]
        direction LR
        KB[(Obsidian KB)]
        GD[Google ecosystem]
        OL[Outlook]
        MT[Meeting transcripts]
        FS[Local files]
        SH[START_HERE.md per project]
    end

    VL <--> Memory
    CC -.reads.-> Memory

    style Memory fill:#fef3c7,stroke:#854d0e,stroke-width:2px
    style Team fill:#e0f2fe,stroke:#0369a1
```

You (or anyone you've shared the KB with) talks to Claude Code. Claude
Code reads VaultLab + memory. VaultLab orchestrates work, writes results
back into the memory. Memory is plain markdown on Google Drive — share
it like any folder, scale across your lab without infrastructure.
