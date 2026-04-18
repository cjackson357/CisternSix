#include <Servo.h>

#include <Servo.h>

Servo esc[5];
Servo dcMotor;  // treat DC motor as servo too

const int ESC_PINS[5] = {3, 5, 6, 9, 10};
const int DC_PIN = 11;  // now safe since Servo library manages it

const int DC_DIR_PIN1 = 12;
const int DC_DIR_PIN2 = 13;

void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("READY");

  for (int i = 0; i < 5; i++) {
    esc[i].attach(ESC_PINS[i], 1000, 2000);
    esc[i].writeMicroseconds(1000);
  }

  dcMotor.attach(DC_PIN, 1000, 2000);
  dcMotor.writeMicroseconds(1500);  // neutral

  pinMode(DC_DIR_PIN1, OUTPUT);
  pinMode(DC_DIR_PIN2, OUTPUT);
  digitalWrite(DC_DIR_PIN1, LOW);
  digitalWrite(DC_DIR_PIN2, LOW);
}

String inputBuffer = "";

void loop() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n') {
      inputBuffer.trim();

      if (inputBuffer == "PING") {
        Serial.println("PONG");
        handshakeDone = true;
      } else if (handshakeDone) {
        parseCommand(inputBuffer);
      }

      inputBuffer = "";
    } else {
      inputBuffer += c;
    }
  }
}

void parseCommand(String cmd) {
  String echo = "DRIVING:";
  int motorValues[6] = {128, 128, 128, 128, 128, 128};

  int start = 0;
  while (start < cmd.length()) {
    int comma = cmd.indexOf(',', start);
    String token = (comma == -1) ? cmd.substring(start) : cmd.substring(start, comma);

    if (token.charAt(0) == 'M') {
      int colon = token.indexOf(':');
      if (colon != -1) {
        int motorId = token.substring(1, colon).toInt() - 1;
        int value   = token.substring(colon + 1).toInt();

        if (motorId >= 0 && motorId < 5) {
          int us = map(value, 0, 255, 1000, 2000);
          esc[motorId].writeMicroseconds(constrain(us, 1000, 2000));
          motorValues[motorId] = value;
        }
        else if (motorId == 5) {
          value = constrain(value, 0, 255);
          motorValues[5] = value;

          if (value == 128) {
            dcMotor.writeMicroseconds(1500);  // neutral/stop
            digitalWrite(DC_DIR_PIN1, LOW);
            digitalWrite(DC_DIR_PIN2, LOW);
          }
          else if (value > 128) {
            int us = map(value, 129, 255, 1500, 2000);
            digitalWrite(DC_DIR_PIN1, HIGH);
            digitalWrite(DC_DIR_PIN2, LOW);
            dcMotor.writeMicroseconds(us);
          }
          else {
            int us = map(value, 0, 127, 2000, 1500);  // reversed
            digitalWrite(DC_DIR_PIN1, LOW);
            digitalWrite(DC_DIR_PIN2, HIGH);
            dcMotor.writeMicroseconds(us);
          }
        }
      }
    }

    if (comma == -1) break;
    start = comma + 1;
  }

  // Send echo back to Pi
  for (int i = 0; i < 6; i++) {
    echo += "M" + String(i + 1) + ":" + String(motorValues[i]);
    if (i < 5) echo += ",";
  }
  Serial.println(echo);
}