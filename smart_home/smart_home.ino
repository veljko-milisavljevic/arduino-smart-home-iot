#include <TimerOne.h>
#include <ServoTimer2.h>
#define Dugme 2
#define PIR 3
#define Echo 4
#define Trig 5
#define Vrata 6
#define Svetlo 8
#define Ventilacija 9
#define Foto A1
#define LM35 A0

bool modVentilacija = false;
bool modOsvetljenje = false;
bool modPIR = false;
bool modGaraza = false;

volatile bool snimi = false;

String PrimljenaPoruka;
volatile float temp;
volatile bool vent = false;
volatile float osv;
volatile bool led = false;
volatile float dist;
volatile bool detektovanPokret = false;
volatile bool snimiPokret = false;
volatile int pirTimer = 0;

volatile bool dugmePritisnuto = false;
volatile bool vrataOtvorena = false;

ServoTimer2 servoVrata;
volatile int ugao = 0;

void TimerPrekid() {
  analogRead(LM35);
  temp = (analogRead(LM35) * 500.0) / 1023;
  osv = constrain(map(analogRead(Foto), 0, 60, 0, 100), 0, 100);

  //Ventilacija
  if (temp > 30) vent = true;
  else if (temp < 24) vent = false;
  digitalWrite(Ventilacija, vent && modVentilacija);

  //Svetlo
  if (dugmePritisnuto) {
    modOsvetljenje = false;
    modPIR = false;
    pirTimer = 0;
    led = !led;
    digitalWrite(Svetlo, led);

    //Serial.print("LED je: ");
    //Serial.println(led);
    //Serial.println("Automatsko svetlo isključeno!");

    dugmePritisnuto = false;
  }

  if (modPIR) {
    if (detektovanPokret && modPIR) {
      Serial.println("Pokret detektovan!");
      pirTimer = 11;
      detektovanPokret = false;
    }

    pirTimer = pirTimer ? --pirTimer : 0;
    led = pirTimer;
  }


  if (modOsvetljenje) digitalWrite(Svetlo, (osv < 30));
  else digitalWrite(Svetlo, led);

  //Garaža
  snimi = true;
}

void DugmePrekid() {
  dugmePritisnuto = true;
}
void PIRPrekid() {
  detektovanPokret = true;
  snimiPokret = true;
  //Serial.println("Pokret detektovan!");
}

void setup() {
  pinMode(Dugme, INPUT_PULLUP);
  pinMode(PIR, INPUT_PULLUP);
  pinMode(Svetlo, OUTPUT);
  pinMode(Ventilacija, OUTPUT);
  pinMode(Foto, INPUT);
  pinMode(LM35, INPUT);
  pinMode(Trig, OUTPUT);
  pinMode(Echo, INPUT);

  Serial.begin(9600);

  attachInterrupt(digitalPinToInterrupt(PIR), PIRPrekid, FALLING);
  attachInterrupt(digitalPinToInterrupt(Dugme), DugmePrekid, FALLING);

  servoVrata.attach(Vrata);

  Timer1.initialize(1000000);
  Timer1.attachInterrupt(TimerPrekid);
}

void loop() {

  if (Serial.available() > 0) {
    PrimljenaPoruka = Serial.readString();
    if (PrimljenaPoruka == "V_ON") {
      //Serial.println("Ventilacija uključena");
      modVentilacija = true;
    } else if (PrimljenaPoruka == "V_OFF") {
      //Serial.println("Ventilacija isključena");
      modVentilacija = false;
    } else if (PrimljenaPoruka == "L_ON") {
      //Serial.println("Automatsko svetlo uključeno");
      modOsvetljenje = true;
      //Serial.println("PIR isključeno");
      modPIR = false;
    } else if (PrimljenaPoruka == "L_OFF") {
      //Serial.println("Automatsko svetlo isključeno");
      modOsvetljenje = false;
    } else if (PrimljenaPoruka == "PIR_ON") {
      //Serial.println("PIR uključeno");
      modPIR = true;
      //Serial.println("Automatsko svetlo isključeno");
      modOsvetljenje = false;
    } else if (PrimljenaPoruka == "PIR_OFF") {
      //Serial.println("PIR isključeno");
      modPIR = false;
    } else if (PrimljenaPoruka == "G_ON") {
      //Serial.println("Garaža uključeno");
      modGaraza = true;
    } else if (PrimljenaPoruka == "G_OFF") {
      //Serial.println("Garaža isključeno");
      modGaraza = false;
    } else if (PrimljenaPoruka == "demo") {
      modGaraza = true;
      modPIR = true;
      modVentilacija = true;
    } else {
      //Serial.println("Poruka nije prepoznata!");
    }
  }


  if (snimi) {
    digitalWrite(Trig, HIGH);
    digitalWrite(Trig, LOW);

    dist = 0.017 * pulseIn(Echo, HIGH);


    if (modGaraza) {
      if (dist < 10) {
        vrataOtvorena = (servoVrata.read() == 750);
        servoVrata.write(1500);
      } else {
        servoVrata.write(750);
      }
    }

    snimi = false;
    //Slanje
    Serial.print(temp);
    Serial.print(" ");
    Serial.print(osv);
    Serial.print(" ");
    Serial.print(vrataOtvorena && modGaraza);
    Serial.print(" ");
    Serial.println(snimiPokret && modPIR);
    vrataOtvorena = false;
    snimiPokret = false;

  }
}
