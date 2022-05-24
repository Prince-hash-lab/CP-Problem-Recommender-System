from prob_class import Problem
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from nltk.corpus import stopwords

def create_word_features(words):
    # print words
    w = []
    for wrd in words.split():
        w.append(wrd)
    useful_words = [word for word in w if word not in
                       stopwords.words('english')]
    my_dict = ' '.join([word for word in useful_words])
    # print my_dict
    return my_dict

def minimizeDescription(desc):
    desc = desc.replace('.', ' ')
    desc = desc.replace(',', ' ')
    desc = create_word_features(desc)
    return desc.lower()

if __name__ == "__main__":
    engine = create_engine('mysql+mysqldb://root:@localhost/data stage fyp')
    conn = engine.connect()

    Session = sessionmaker(bind=engine)
    s = Session()

    probs = s.query(Problem)
    count = 1
    for p in probs:
        # print p.description
        try:
            # p.description = create_word_features(p.description)
            desc = p.modified_description
            desc = desc.replace('.', ' ')
            desc = desc.replace(',', ' ')
            desc = create_word_features(desc)
            # print desc
            # print "success " + p.prob_code
            p.modified_description = desc.lower()
            s.commit()
            #print 'done: '+p.prob_code
            print('{0} out of {1} {2} success'.format(str(count), str(probs.count()), p.prob_code))
        except:
            #print "failed " +p.prob_code
            print('{0} out of {1} {2} failed'.format(str(count), str(probs.count()), p.prob_code))
        finally:
            count += 1

        # print desc
        # print