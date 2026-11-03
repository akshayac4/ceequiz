from django.core.management.base import BaseCommand
from django.db import transaction

from quiz.models import District, Option, Question, Quiz

GUJARAT_DISTRICTS = [
    ("Ahmedabad", "અમદાવાદ"),
    ("Amreli", "અમરેલી"),
    ("Anand", "આણંદ"),
    ("Aravalli", "અરવલ્લી"),
    ("Banaskantha", "બનાસકાંઠા"),
    ("Bharuch", "ભરૂચ"),
    ("Bhavnagar", "ભાવનગર"),
    ("Botad", "બોટાદ"),
    ("Chhota Udepur", "છોટાઉદેપુર"),
    ("Dahod", "દાહોદ"),
    ("Dang", "ડાંગ"),
    ("Devbhoomi Dwarka", "દેવભૂમિ દ્વારકા"),
    ("Gandhinagar", "ગાંધીનગર"),
    ("Gir Somnath", "ગીર સોમનાથ"),
    ("Jamnagar", "જામનગર"),
    ("Junagadh", "જૂનાગઢ"),
    ("Kheda", "ખેડા"),
    ("Kutch", "કચ્છ"),
    ("Mahisagar", "મહીસાગર"),
    ("Mehsana", "મહેસાણા"),
    ("Morbi", "મોરબી"),
    ("Narmada", "નર્મદા"),
    ("Navsari", "નવસારી"),
    ("Panchmahal", "પંચમહાલ"),
    ("Patan", "પાટણ"),
    ("Porbandar", "પોરબંદર"),
    ("Rajkot", "રાજકોટ"),
    ("Sabarkantha", "સાબરકાંઠા"),
    ("Surat", "સુરત"),
    ("Surendranagar", "સુરેન્દ્રનગર"),
    ("Tapi", "તાપી"),
    ("Vadodara", "વડોદરા"),
    ("Valsad", "વલસાડ"),
]

# order, text_en, text_gu, options[(label, en, gu)]  — correct option intentionally left unset.
QUESTIONS = [
    (
        1,
        "Which of the following schemes do NOT directly link with a clean, green, safe and sustainable school framework?",
        "નીચેની કઈ યોજના સ્વચ્છ, હરિયાળી, સુરક્ષિત અને ટકાઉ શાળાના માળખા સાથે સીધી રીતે જોડાયેલી નથી?",
        [
            ("A", "Mission LiFE", "મિશન LiFE"),
            ("B", "School Safety Programme", "શાળા સુરક્ષા કાર્યક્રમ"),
            ("C", "PM eVidhya scheme", "PM eVidya યોજના"),
            ("D", "Ek Ped Maa ke Naam", "એક પેડ માઁ કે નામ"),
        ],
    ),
    (
        2,
        "What is the adequate drinking water requirement per child per day in a non-residential day school?",
        "Non-residential day Schoolમાં દરરોજ એક બાળક દીઠ પીવાના પાણીની પૂરતી જરૂરિયાત કેટલી છે?",
        [
            ("A", "5 liter", "5 લિટર"),
            ("B", "3 liter", "3 લિટર"),
            ("C", "2.5 liter", "2.5 લિટર"),
            ("D", "1.5 liter", "1.5 લિટર"),
        ],
    ),
    (
        3,
        "Global Handwashing Day is celebrated on:",
        "Global Handwashing Day ક્યારે ઉજવાય છે?",
        [
            ("A", "19th November", "19 નવેમ્બર"),
            ("B", "15th October", "15 ઓક્ટોબર"),
            ("C", "28th May", "28 મે"),
            ("D", "5th June", "5 જૂન"),
        ],
    ),
    (
        4,
        "According to MoEFCC and Central Pollution Control Board, the 'Good' Air Quality Index (AQI) which is safe for children should be less than:",
        "MoEFCC અને કેન્દ્રીય પ્રદૂષણ નિયંત્રણ બોર્ડ (CPCB) મુજબ, બાળકો માટે સલામત ગણાતો 'સારો' હવા ગુણવત્તા સૂચકાંક (AQI) કેટલાથી ઓછો હોવો જોઈએ?",
        [
            ("A", "50", "50"),
            ("B", "100", "100"),
            ("C", "150", "150"),
            ("D", "200", "200"),
        ],
    ),
    (
        5,
        "Which of the following is a climate resilient action for safe air quality in schools",
        "શાળામાં સ્વચ્છ હવા માટે નીચેનામાંથી કયું પગલું આબોહવા-સહનશીલ (ક્લાયમેટ રેઝિલિયન્ટ) છે?",
        [
            ("A", "Burn dry leaves and paper waste on campus to keep the school clean", "શાળા સ્વચ્છ રાખવા માટે પરિસરમાં સૂકાં પાંદડાં અને કાગળનો કચરો બાળવો"),
            ("B", "Use firewood or coal to cook the mid-day meal", "મધ્યાહ્ન ભોજન રાંધવા માટે લાકડાં કે કોલસાનો ઉપયોગ કરવો"),
            ("C", "Keep windows closed during cleaning so dust stays inside the room", "સફાઈ વખતે બારીઓ બંધ રાખવી, જેથી ધૂળ ઓરડામાં જ રહે"),
            ("D", "Ensure 'No Vehicle Zone' in schools", "શાળામાં 'નો વ્હીકલ ઝોન' રાખવો"),
        ],
    ),
    (
        6,
        "Which of the following is NOT a contribution of green spaces in schools",
        "શાળામાં હરિયાળી જગ્યાનું નીચેનામાંથી કયું યોગદાન નથી?",
        [
            ("A", "Positive impact on children's health and mental wellbeing", "બાળકોના સ્વાસ્થ્ય અને માનસિક સુખાકારી પર સારી અસર"),
            ("B", "Reduce water percolation underground", "જમીનમાં પાણી ઊતરવાનું ઘટાડે છે"),
            ("C", "Regulate temperature and reduce heat stress", "તાપમાન નિયંત્રિત કરે છે અને ગરમીનો તણાવ ઘટાડે છે"),
            ("D", "Conserve soil and support biodiversity", "જમીનનું રક્ષણ કરે છે અને જૈવવિવિધતાને ટેકો આપે છે"),
        ],
    ),
    (
        7,
        "Which of the following is a green action by schools under the energy component?",
        "ઊર્જા ઘટક હેઠળ શાળાઓ માટે નીચેનામાંથી કયું હરિત (ગ્રીન) પગલું છે?",
        [
            ("A", "Keep lights and fans on all day for ready for use classrooms", "વર્ગખંડો વાપરવા માટે તૈયાર રહે તે માટે આખો દિવસ લાઈટ અને પંખા ચાલુ રાખવા"),
            ("B", "Prefer cost over star rating of air conditioner when buying", "એર કન્ડિશનર ખરીદતી વખતે સ્ટાર રેટિંગ કરતાં કિંમતને વધુ મહત્ત્વ આપવું"),
            ("C", "Switch to higher star rating appliances and use renewable energy", "વધુ સ્ટાર રેટિંગવાળાં ઉપકરણો વાપરવાં અને નવીનીકરણીય (રિન્યુએબલ) ઊર્જાનો ઉપયોગ કરવો"),
            ("D", "Energy conservation is not the responsibility of school", "ઊર્જા બચાવવી એ શાળાની જવાબદારી નથી"),
        ],
    ),
    (
        8,
        "A climate responsive school building will NOT follow the following:",
        "આબોહવાને અનુકૂળ શાળા ઇમારત નીચેનામાંથી કયું નહીં કરે?",
        [
            ("A", "Providing chajjas/ box shading at all the windows in the south and west side", "દક્ષિણ અને પશ્ચિમ બાજુની બધી બારીઓ પર છજ્જા/બોક્સ શેડિંગ આપવું"),
            ("B", "Using M.S. in coastal areas instead of CRS (Corrosion-resistant steel) and wood", "દરિયાકાંઠાના વિસ્તારોમાં CRS (કાટ-પ્રતિરોધક સ્ટીલ) અને લાકડાને બદલે M.S. વાપરવું"),
            ("C", "Ensuring strong boundary wall for the school that is all weather proof", "દરેક ઋતુમાં ટકી રહે તેવી મજબૂત દીવાલ બનાવવી"),
            ("D", "Fixing dilapidated roofs, loose metal boards and loose open wires", "જર્જરિત છત, ઢીલાં ધાતુનાં પાટિયાં અને ખુલ્લા ઢીલા વાયરો સુધારવા"),
        ],
    ),
    (
        9,
        "A safe and inclusive school is NOT the one that",
        "સુરક્ષિત અને સર્વસમાવેશક શાળા એવી શાળા નથી કે જે…",
        [
            ("A", "Allows corporal punishment to some extent", "અમુક હદ સુધી શારીરિક સજાની છૂટ આપે"),
            ("B", "Has a child protection policy in place to prevent sexual offences and abuse against children", "બાળકો સામે જાતીય ગુના અને શોષણ અટકાવવા માટે બાળ સુરક્ષા નીતિ ધરાવે"),
            ("C", "Has ramps for CWSN students to access toilets, classrooms, handwash points etc.", "વિશેષ જરૂરિયાતવાળા બાળકો (CWSN) માટે શૌચાલય, વર્ગખંડ, હાથ ધોવાની જગ્યા વગેરે સુધી પહોંચવા રેમ્પ ધરાવે"),
            ("D", "Has gender segregated toilets", "છોકરા અને છોકરીઓ માટે અલગ શૌચાલય ધરાવે"),
        ],
    ),
    (
        10,
        "Which of the following aspects is NOT a part of Saksham Shala Action Plan",
        "સક્ષમ શાળા એક્શન પ્લાનનો ભાગ નીચેનામાંથી કયો નથી?",
        [
            ("A", "Challenges / gaps", "પડકારો / ખામીઓ"),
            ("B", "Target star rating", "લક્ષ્ય સ્ટાર રેટિંગ"),
            ("C", "Disasters faced by school", "શાળાએ સામનો કરેલી આપત્તિઓ"),
            ("D", "Interventions requiring financial and non financial support", "જેના માટે નાણાકીય અને બિન-નાણાકીય સહાય જરૂરી છે તેવા હસ્તક્ષેપો"),
        ],
    ),
]


class Command(BaseCommand):
    help = "Seed Gujarat districts and the first State-level Workshop quiz (10 questions, correct answers left unset)."

    @transaction.atomic
    def handle(self, *args, **options):
        for name_en, name_gu in GUJARAT_DISTRICTS:
            District.objects.get_or_create(name_en=name_en, defaults={"name_gu": name_gu})
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(GUJARAT_DISTRICTS)} districts."))

        quiz, created = Quiz.objects.get_or_create(
            title_en="State-level Workshop, 1 Oct 2026 – Clean, Green, Safe and Climate Resilient Schools",
            defaults={
                "title_gu": "રાજ્ય-સ્તરીય કાર્યશાળા, 1 ઓક્ટોબર 2026 – સ્વચ્છ, હરિયાળી, સુરક્ષિત અને આબોહવા-સહનશીલ શાળાઓ",
                "event_name": "State-level Workshop, VSK SSA Gandhinagar",
                "audience": Quiz.AUDIENCE_TEACHER,
                "duration_minutes": 10,
            },
        )

        for order, text_en, text_gu, options in QUESTIONS:
            question, _ = Question.objects.update_or_create(
                quiz=quiz, order=order, defaults={"text_en": text_en, "text_gu": text_gu}
            )
            for label, opt_en, opt_gu in options:
                Option.objects.update_or_create(
                    question=question, label=label, defaults={"text_en": opt_en, "text_gu": opt_gu}
                )

        self.stdout.write(self.style.SUCCESS(
            f"Seeded quiz '{quiz.title_en}' with {len(QUESTIONS)} questions (code={quiz.code}). "
            "Tick the correct option for each question in the admin before opening the pre-test."
        ))
