// Read-only, allowlisted by asset_io.py. Skip archive-wide list/attribute loading.
#include <StormLib.h>
#include <cstring>
int main(int argc,char** argv){
 if(argc!=5 || std::strcmp(argv[1],"extract"))return 2;
 HANDLE archive=nullptr;
 if(!SFileOpenArchive(argv[2],0,STREAM_FLAG_READ_ONLY|MPQ_OPEN_NO_LISTFILE|MPQ_OPEN_NO_ATTRIBUTES,&archive))return 3;
 bool ok=SFileExtractFile(archive,argv[3],argv[4],SFILE_OPEN_FROM_MPQ);
 SFileCloseArchive(archive);return ok?0:4;
}
