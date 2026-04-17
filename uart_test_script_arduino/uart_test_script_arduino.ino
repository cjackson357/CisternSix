String inputBuffer = "";

void setup() {
  Serial.begin(115200);
}

void loop() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n') {
      inputBuffer.trim();
      if (inputBuffer == "PING") {
        Serial.println("PONG");
      }
      inputBuffer = "";
    } else {
      inputBuffer += c;
    }
  }
}