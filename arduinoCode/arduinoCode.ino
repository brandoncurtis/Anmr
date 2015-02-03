/* Daniel Hon Kit Chong and Carl Michal
 Date edited: January 2012
 
 Program: This program takes in inputs from a host computer to use as
 	    instructions to control hardware and receive signals.
 
 */


#include <avr/wdt.h>
#include "definitions.h"

#ifndef cbi
#define cbi(sfr,bit) (_SFR_BYTE(sfr) &= ~_BV(bit))
#endif
#ifndef sbi
#define sbi(sfr,bit) (_SFR_BYTE(sfr) |= _BV(bit))
#endif


// convert from ms and us to clock cycles (at 16 MHz)
#define CONV_MS 16000UL
#define CONV_US 16UL

#define  SLOP 300U // how many cycles advance we think we need.
#define SLOP2 200U //these look to be 150 or so bigger than needed.


// ring buffer for data captured from ADC
#define RINGLENGTH 8        //what size the buffer is
volatile int wring=0,rring=0;// wwring is where to next write, rring is where to next read
volatile int dbuff[RINGLENGTH]; // the buffer
volatile unsigned long count=0;// how many data points we've captured.

//Function prototypes
//however, I did notice that only the function calls within the setup function are ever prototyped
//note: though the arduino IDE doesn't require function prototypes, scons does

void Pulse4(unsigned long hperiods, int phase);
void high_res_init();
void high_res_delay(unsigned long cycles);
void SetupTimer1synth(int hperiod);
void SetupADC();
void StartAcq();
unsigned long readLongVal(int bytes, byte* ptr);
byte fRead(int bytes,byte *ptr);
unsigned int readVal(int bytes, byte* ptr);

// sequence parameters

//pointers for allocated memory;
byte* head = NULL;
byte* ptr = NULL;

byte* loopPtr = NULL;
int loopCounter = 0;
unsigned long scanNum = 0;

unsigned int delc1 = 0;
unsigned int delc2 = 0; // duration of the off and on times in each half cycle
unsigned int hperiod = 0;
unsigned int fperiod = 0;  //period, halfperiod
unsigned char ppin = 2;
unsigned char mpin = 3;
unsigned int bytes = 0;
unsigned long checksum1 = 0;
unsigned long checksum2 = 0;
byte *tables[16]; // pointers to the phase tables
byte tlens[16]; // lengths of the tables


unsigned long  np = 0; // points to read in, now an input from host program
unsigned long totalNumReadings=0;


void setup(){

  for (int i = 2; i<13;i++)
  {
    pinMode(i,OUTPUT);  //we want to set everything else to output mode
    digitalWrite(i,LOW); // and turned off.
  }
  pinMode(9,INPUT); // sync signal

  Serial.begin(1000000);

  // turn off some components we don't need.  Should help noise a little, and power use
  sbi(PRR,PRTWI); // two-wire serial interface
  sbi(PRR,PRSPI);// spi interface not needed
  sbi(ACSR,ACD); //turn off analog comparator

  //turn off watchdog timer:
  //this means that Timer() will not work
  MCUSR = 0;
  wdt_disable();

  high_res_init(); // prep timer 2 for counting high res delays.
  SetupADC();
}

void loop(){
  //contact has been established
  //reinitialising local variables for reading in parameters
  int readPhase;
  int input;
  int done = 0;
  int pinNum, state, edge, prior, post, phase, numMS ;
  int phaseInc,phaseMod;
  unsigned long numCS, numHalfPeriods;
  unsigned long rcount =0;
  input =0;
  // enable timer 0 overflow interrupts
  sbi(TIMSK0,TOIE0); // reenable timer0 overflows
  while(!input)  //awaiting startSignal
  {
    if (Serial.available())  //then buffer not empty
    {
      input = Serial.read();
    }
    else
    {
      delay(5);
    }
  }

  switch(input){
  case QUERY:
    Serial.println("ANMR v0.9, Ready");
    break;
  case START_OF_PROGRAM://if (input == %0001)    //start of program instruction
    {
      scanNum = 0;
      checksum1 = 0;
      checksum2 = 0;
      if (head != NULL)            //there is a pulse program stored
        free (head);               
      bytes=0;
      totalNumReadings=0;
      if (fRead(2,(byte *) &bytes) == 0){
        Serial.println("Timed out reading number of bytes");
      }
      if(fRead(4,(byte *)&totalNumReadings)==0){
        Serial.println("Timed out reading number of readings");
        break;
      }
      head = (byte *) malloc ( bytes * sizeof (byte) );

      if (head == NULL)      //malloc failed
      {
        Serial.println("Malloc failed!");
        break;
      }
      else
        Serial.println("Malloc successful");

      if (fRead(bytes,head) == 0){
        Serial.println("Timed out reading program" );
        free(head);
        break;
      }
      else{
        for (int i =0; i < bytes; i++)
        {
          checksum1 += (i+1)*head[i];
          checksum2 += (i+2)*head[i];
        }
        Serial.println(checksum1,DEC);
        Serial.println(checksum2,DEC);
      }
    }
    break;

  case GO:                        //execute procedure
    {
      hperiod = 0; // frequency not set yet.
      fperiod = 0;


      ptr = head;
      done = 0;
      if (head != NULL) //then thunderbirds are go
      {
        Serial.println("Executing instructions");
      }
      else            //then no instructions
      {
        Serial.println("Execution failed");
        break;
      }
      cbi(TIMSK0,TOIE0); // disable timer 0 overflow interrupts
      cli(); //disable all interrupts
      while (!done)
      {
        input = *ptr;
        ptr ++;
        switch(input)
        {
        case DELAY_IN_CLOCKS: //else if (input == %0010)    //delay(in clock cycles)
          {
            numCS = readLongVal(4, ptr);
            ptr += 4;
            high_res_delay(numCS);
          }
          break;
        case DELAY_IN_MS: //else if (input == % 0011)  //delay(in ms)
          { 
            numMS = readVal(2, ptr);
            ptr += 2;
            high_res_delay(numMS * CONV_MS);
          }
          break;
          //optimise: there are only 14 digital pins, and analog pins are unused
        case TOGGLE_PIN:
          { // parameters are pinNum and starting state
            unsigned char myval;
            pinNum = readVal(1,ptr);
            ptr+= 1;
            state = readVal(1,ptr);
            ptr+= 1;
            myval = state + (scanNum&1);
            digitalWrite(pinNum,(myval&1));
          }
          break;
        case CHANGE_PIN: //else if (input == % 0100)  //change Pin 
          {
            pinNum = readVal(1, ptr);
            ptr += 1;
            state = readVal(1, ptr);
            ptr += 1;
            pinMode(pinNum, OUTPUT);
            digitalWrite(pinNum,(state &1));
            /*            if (state)
             digitalWrite(pinNum, 1);
             else
             digitalWrite(pinNum, 0);
             */
          }
          break;
        case WAIT_FOR_PIN:                   //wait for Pin edge
          {
            pinNum = readVal(1, ptr);
            ptr += 1;
            edge = readVal(1, ptr);
            ptr += 1;
            pinMode(pinNum, INPUT);
            prior = digitalRead(pinNum);
            if (edge == 1)        //wait for rising edge
              while (prior)
                prior = digitalRead(pinNum);
            else if (edge > 1)   //wait for falling edge
              while (!prior)      
                prior = digitalRead(pinNum);
            post = prior;
            while (prior == post) //any old edge will do
              post = digitalRead(pinNum);
          }    
          break; 
        case PULSE:                            //pulse
          {
            /* reads either 4 values: 
             	       - starting phase (int, one byte)
             	       - phase increment(int, one bytes)
             	       - how many scans between increments (int, one byte)
             	       - number of half cycles in the pulse (int, two bytes)
             or:
             - a table number (one byte)
             - number of half cycles in the pulse (two bytes)
             phases are in 2 degree increments
             	    */
            phase=readVal(1,ptr);
            ptr+=1;
            if (phase < 180) {
              phase *= 2;
              phaseInc=readVal(1,ptr)*2;
              ptr+=1;
              phaseMod=readVal(1,ptr);
              ptr+=1;
              // hmm, watch for overflows. phaseInc*scanNum/phaseMod could become large.
              phase = (int) ((((long) phase) + 
                ((long) phaseInc)*(scanNum/ ((long) phaseMod)))%360);
            }
            else{ // phase holds the table number
              byte tnum = phase;
              byte *ptr;
              ptr = tables[tnum];
              phase = ptr[scanNum%tlens[tnum]]*2;
            }
            numHalfPeriods = readLongVal(2, ptr);
            ptr += 2;

            Pulse4(numHalfPeriods, phase); 
          }    
          break;
        case READ_DATA:                          //read data
          {
            unsigned int ontime,diff;
            byte extra=0;
            int mult;

            sbi(ADCSRA,ADSC); // start an ADC conversion. First conversion is slow
            // and reference needs to stabilize.

            sei(); // reenable interrupts-needed for acquisistions
            /* reads 4 values: 
             	       - starting phase (int, one bytes)
             	       - phase increment(int, one bytes)
             	       - how many scans between increments (int, one byte)
             	       - number of points to read (int, four bytes) 
             or 
             - table number, one byte
             - number of points to read, four bytes         */
            readPhase=readVal(1,ptr);
            ptr+=1;
            if (readPhase < 180){
              readPhase *= 2;
              phaseInc=readVal(1,ptr)*2;
              ptr+=1;
              phaseMod=readVal(1,ptr);
              ptr+=1;

              // hmm, watch for overflows. phaseInc*scanNum/phaseMod could become large.
              readPhase = (int) ((((long) readPhase) + 
                ((long) phaseInc)*(scanNum/ ((long) phaseMod)))%360);
            }
            else{ // phase holds the table number
              byte tnum = readPhase;
              byte *ptr;
              ptr = tables[tnum];
              readPhase = ptr[scanNum%tlens[tnum]]*2;
            }

            np = readLongVal(4, ptr);
            ptr += 4;

            // wait till first conversion is complete.

            // tell that we're sending data
            Serial.println("DAT");
            // how many points:
            Serial.write((byte *) &np ,4); 


            // make sure initial conversion is done
            do{
            } 
            while (bit_is_set(ADCSRA,ADSC));

            // wait for phase:

            // its possible that hperiod and fperiod haven't been set
            if (hperiod != 0){
              extra += readPhase/180;	    
              ontime = ((readPhase-180*extra)*((unsigned long) hperiod))/180UL; 
              //            extra += ontime/hperiod; // not necessary, ontime is always < hperiod
              //            ontime = ontime%hperiod;

              //              diff = ((unsigned int)TCNT1+SLOP2)%fperiod;
              diff = ((unsigned int)TCNT1+SLOP2);
              diff = diff - hperiod * (diff >=fperiod);

              if (diff < ontime+hperiod && diff >= ontime)
              {
                ontime += hperiod;
                extra += 1;    
              } // second half, fine.
              //              if ( (readPhase/180+ extra)%2 == 0)
              if ( (extra & 1) == 0)
                mult = 1;
              else
                mult = -1;

              // wait till our ontime:
              sbi(TIFR1,OCF1A); // make sure the overflow bit is clear
              OCR1A = ontime; // go
              do{ 
              } 
              while (bit_is_clear(TIFR1,OCF1A));
            }
            else 
              mult = (readPhase/180)*2 - 1; // gives 1 or -1 only
            // freq hasn't been set.  Just go asap, and phase 1/-1


            /*          // testing...
             int stime;
             stime =TCNT1;
             Serial.write((byte *) &stime,2);
             */

            StartAcq();

            rcount = 0; // how many points we've sent upstream.

            //Read data and write it through serial to host computer
            do{
              if (wring != rring)
              { // there's a point to read:
                dbuff[rring] = (dbuff[rring]-512) * mult;   // alternate
                Serial.write((byte *) &dbuff[rring],2); // send it up
                //                rring = (rring+1)%RINGLENGTH;
                rring = rring +1;
                rring = rring - RINGLENGTH *(rring >= RINGLENGTH);
                rcount += 1;
              }
            }
            while (rcount < np);

            cli(); // disable interrupts
            //            Serial.println("DEB");
            //            Serial.write((byte *)&mult,2);

          } // end read_data
          break;
        case END_OF_PROGRAM:                         //end of program
          {
            scanNum ++;
            sei(); // enable interrupts for timer and serial read/write

            Serial.println("EOP");
            done = 1;
          }   
          break;
        case SET_FREQ:
          {
            //these are global variables
            delc1 = readVal(2, ptr);
            ptr += 2;
            delc2 = readVal(2, ptr);
            ptr += 2;
            hperiod = readVal(2, ptr);
            ptr += 2;
            fperiod = 2 * hperiod;

            SetupTimer1synth(hperiod);
          }
          break;
        case SET_PULSE_PINS:
          {
            //these are global variables
            ppin = readVal(1, ptr);
            ptr += 1;
            mpin = readVal(1, ptr);
            ptr += 1;
          }
          break;
        case LOOP:
          {
            loopCounter = readVal(2,ptr);
            ptr += 2;
            loopPtr = ptr;  //since 2 bytes are taken for the number of loops
            //and we want to not read this instruction when looping

            break;
          }
        case END_LOOP:
          {
            loopCounter --;
            if (loopCounter > 0)
              ptr = loopPtr;
            break;
          }
        case SYNC:
          {
            sbi(TIFR1,OCF1B);
            do { 
            } 
            while (bit_is_clear(TIFR1,OCF1B));
            break;
          }
        case TABLE:
          // defines a phase table. Assume table number is valid - compiler should have checked
          {   
            byte tnum,tlen;       
            tnum = readVal(1,ptr);
            ptr += 1;
            tlen = readVal(1,ptr);
            ptr+=1;
            tables[tnum]=ptr;
            tlens[tnum]=tlen;
            ptr+=tlen;
          }       
          break;
        default:
          {
            //error! not an instruction byte
            done = 1;
            sei(); // reenable interrupts-needed for acquisistions
            break;
          }

        }
      }
    }// end GO
    break;
  default:
    {
      Serial.println("Unknown Instruction!");  // for testing purposes
    }
    break;
  }
}

void Pulse4(unsigned long hperiods, int phase){
  // arguments are number of half periods, and phase in degrees
  // if phase is 0, pulse goes low first, else, pulse goes high first
  // phase is always 0 - 359

  // this does a pulse with reduced duty cycle to minimize harmonics: -| |--| |--

  // hperiod is the number of clock cycles in a half period.
  // hperiods is the number of half periods in our pulse

    unsigned int ontime1,offtime1,ontime2,offtime2;
  unsigned int diff;
  byte extra=0;

  unsigned long first,second,i;

  // calculate on and off times
  extra = phase/180;
  //  ontime1 = delc1+((phase%180)*((unsigned long) hperiod))/180UL; //ontime is "time we turn on"
  ontime1 = delc1+((phase-180*extra)*((unsigned long) hperiod))/180UL; //ontime is "time we turn on"

  extra += ontime1/hperiod;
  //  ontime1=ontime1%hperiod;
  ontime1=ontime1-hperiod*(ontime1 >=hperiod);

  // now, are we starting in the current half period or one of the next 3?

  //  diff = ((unsigned int)TCNT1+SLOP)%fperiod;
  diff = ((unsigned int)TCNT1+SLOP);
  diff = diff - fperiod * (diff >= fperiod);

  if (diff < ontime1){
  } // good to go.
  else if (diff < ontime1+hperiod)
  {
    ontime1+=hperiod;
    extra += 1;    
  } // second half, fine.
  /* modulo is a function call! very slow!
   offtime1 = (ontime1+delc2)%fperiod; 
   ontime2 = (ontime1+hperiod)%fperiod;
   offtime2 = (offtime1+hperiod)%fperiod;
   */
  offtime1 = ontime1 + delc2;
  offtime1 = offtime1 - fperiod *(offtime1 >= fperiod);
  ontime2 = ontime1+hperiod;
  ontime2 = ontime2 - fperiod *(ontime2 >= fperiod);
  offtime2 = offtime1 +hperiod;
  offtime2 = offtime2 - fperiod *(offtime2 >= fperiod);
  // now, figure out if we go + or - first, then get started.
  //  if ( (phase/180+ extra)%2 == 0){
  if ( (extra&1) == 0){
    first=ppin;
    second=mpin;
  }
  else{
    first=mpin;
    second=ppin;
  }

  for(i=0;i<hperiods;i+=2){
    // ok get started.
    sbi(TIFR1,OCF1A); // make sure the overflow bit is clear
    OCR1A = ontime1; // go

    do{
    }
    while (bit_is_clear(TIFR1,OCF1A));
    digitalWrite(first,HIGH);

    sbi(TIFR1,OCF1A); // make sure the bit is clear
    OCR1A = offtime1; 
    do{
    }
    while (bit_is_clear(TIFR1,OCF1A));
    digitalWrite(first,LOW);

    //    if ( i < hperiods-1 || hperiods%2 == 0){
    if ( i < hperiods-1 || (hperiods & 1) == 0){
      sbi(TIFR1,OCF1A); // make sure the bit is clear
      OCR1A = ontime2;
      do{
      } 
      while (bit_is_clear(TIFR1,OCF1A));
      digitalWrite(second,HIGH);

      sbi(TIFR1,OCF1A); // make sure the bit is clear
      OCR1A = offtime2;
      do{
      } 
      while (bit_is_clear(TIFR1,OCF1A));
      digitalWrite(second,LOW);
    }

  }
  /* // testing:
   unsigned int stime;
   stime = TCNT1;
   Serial.write((byte *) &stime,2);
   */
}

//This is simply initialising timer2 to be a high precision timer
//going to assume it works as advertised

void high_res_init(){
  //Timer clock = 16MHz / prescale, see datasheet, table 17-9 on page 163.
  // 111 = /1024, 110=/256 101=/128, 100=/64, 011=/32, 010=/8, 001=/1
  // these prescalers may not be right for timer 1!  011 is /64?
  // I want normal mode here: counts up to specified top value, then clears and starts over.
  // WGM to 0 just counts and sets overflow flag when full.

  TCCR2A = 0;
  TCCR2B = 0<<CS22 |0<<CS21 | 1 <<CS20; 
  TIMSK2= 0;
}

void high_res_delay(unsigned long cycles){
  unsigned long maxc=256; // 8 bits.
  unsigned long overflows;
  unsigned long i;
  byte tval;
  // looks like I have about 110 cycles of overhead, 


  // should probably subtract a correction factor off of cycles for overhead...
  cycles -= 104;

  // how many overflows do we need?
  overflows=cycles/maxc;
  tval=maxc-1- (cycles-overflows*maxc);
  // set TCNT to the remainder:  do it this way to try to make sure we don't screw up for a short remainder.

  TCNT2=0;
  sbi(TIFR2,TOV2);// clear overflow bit.
  TCNT2= tval; // we just started counting.
  for(i=0;i<overflows+1;i++){
    do{
    }
    while(bit_is_clear(TIFR2,TOV2)); // in case something wrong woke us up.
    sbi(TIFR2,TOV2); // clear the interrupt flag

  }

  return;

}

/* SetupTimer1synth
 Configures the ATMega328 16-Bit Timer1 
 Puts it into CTC mode which clears at the number of counts specified in OCR1A
 */

void SetupTimer1synth(int hperiod){
  unsigned int hp;
  //Timer clock = 16MHz / prescale, see datasheet.  CS1 2:0 are prescaler bits:
  // 111 = /1024, 110=/256 101=/128, 100=/64, 011=/32, 010=/8, 001=/1

  // I want CTC mode: counts up to specified top value, then clears and starts over.
  // setting WGM13:0 to 1100 sets CTC mode with TOP defined by ICR1



  TCCR1A = 0<<WGM11 | 0 <<WGM10;
  TCCR1B = 1<<WGM13| 1<<WGM12|0<<CS12 | 0<<CS11 | 1 <<CS10; 
  TCCR1C = 0;

  // each counting rollover is a whole period.  Want it to be an even number of tics though:
  hp=hperiod;
  ICR1 = 2*hp-1; 

  TIMSK1 = 0<<TOIE1; 
  OCR1B = 2*hp-1; // we'll use OCF1B just like an overflow.
  // apparently the overflow bit gets cleared by itself?
  TCNT1 = 0;// reset the timer and go.
  return;
}

ISR(ADC_vect){
  uint8_t  low,high;
  // grab the data from the last conversion.
  low=ADCL;
  high=ADCH;

  count+=1;

  // are we finished?
  if(count == np-1){  // the last conversion triggered itself already.
    cbi(ADCSRA,ADATE); // turn off ADC auto trigger.
  }

  // store data in ring buffer so it can be read out:
  if (count <= np) {
    dbuff[wring] = (high<<8)|low;
    //    wring = (wring+1)%RINGLENGTH;
    wring += 1;
    wring = wring - RINGLENGTH *(wring >= RINGLENGTH);
  }

  //  if (count %2 == 0)
  // digitalWrite(12,(count/2)%2);

  // we may accidentally do one extra conversion, but it just wastes a little time at the end.
}


void StartAcq(){
  rring=0;
  wring=0;
  count = 0; // how many points the ADC has acquired
  sbi(ADCSRA,ADATE); // enable ADC auto trigger
  sbi(ADCSRA,ADSC);  //go.
}

void SetupADC(){
  // do this to set the MUX to read from the pin we want.
  analogRead(0);
  // turn off digital input buffer on channel used for channel 1 input
  DIDR0 = 0x01;
  // set ADC auto trigger - free running mode.  retriggers on its own interrupt flag.
  ADCSRB |= 0<<ADTS2 | 0 <<ADTS1 | 0<< ADTS0; 

  sbi(ADCSRA,ADIE);// enable ADC interrupts:
}


byte fRead(int bytes,byte *ptr){
  /* reads specified number of bytes from the serial port, checking for timeout.
   loads them into the given pointer starting from the beginning */
  for(int i=0;i<bytes;i++){
    if (!Serial.available()){
      for (unsigned long j=0;j<1060000UL;j++){
        if (Serial.available()){
          break;
        }
        if (j>=1059999UL) return 0;
      }
    }
    ptr[i] = Serial.read();
  }
  return 1;
}


unsigned int readVal(int bytes, byte* ptr){
  int i;
  unsigned val=0;
  byte *temp;
  temp = (byte *) &val;

  for (i=0;i<bytes;i++)
    temp[i]=ptr[i]  ;

  return val;
}

unsigned long readLongVal(int bytes, byte* ptr){
  int i;
  byte *temp;
  unsigned long val = 0;

  temp = (byte *) &val;
  for (i=0;i<bytes;i++)
    temp[i] = ptr[i];

  return val;
}


