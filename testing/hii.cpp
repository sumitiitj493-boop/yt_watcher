#include <iostream>
using namespace std;

int main() {
    for (int i = 0; i < 260; i++) {
        unsigned char c = i;
        cout << i << " -> " << (int)c << endl;
    }
}