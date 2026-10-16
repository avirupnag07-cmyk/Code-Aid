# Java diagnostic fixture

`Broken.java` returns from a non-void method without a value on line 2.
The adapter invokes `javac` with annotation processing disabled and writes
class output to a temporary directory; it never runs the class.

Expected diagnostic: `Broken.java`, line 2, error, tool `javac`.
