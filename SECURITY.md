# Security

Gyroid Filter runs a small web server **only on your own computer** (`127.0.0.1`, random port). It checks the `Host` header and a secret token generated at each start, and writes files only to the Cura plug-in folder when you press *Install* (it reads the copy back to check it).

If you find a way around that, or any other security problem, please report it **privately** through GitHub: the repository's *Security* tab, *Report a vulnerability*. Please do not open a public issue for it.

This is a work-in-progress hobby project and comes with no warranty (see [LICENSE.md](LICENSE.md)).
