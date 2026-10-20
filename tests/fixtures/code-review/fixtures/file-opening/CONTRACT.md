# File opening
The renderer may request an ordinary local file. The IPC boundary requires a trusted sender and an absolute path. The OS decides actual file readability. Invalid input, an untrusted sender, and OS permission errors remain errors. The renderer's preliminary validation is only a user hint. No per-file grants or catalog are required.
